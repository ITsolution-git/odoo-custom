#-----------------------------------------------------------
# Threaded, Gevent and Prefork Servers
#-----------------------------------------------------------
import datetime
import errno
import fcntl
import logging
import os
import os.path
import platform
import psutil
import random
import resource
import select
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback

import werkzeug.serving
try:
    from setproctitle import setproctitle
except ImportError:
    setproctitle = lambda x: None

import openerp
import openerp.tools.config as config
from openerp.release import nt_service_name
from openerp.tools.misc import stripped_sys_argv

import wsgi_server

_logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 60 # 1 min

#----------------------------------------------------------
# Werkzeug WSGI servers patched
#----------------------------------------------------------

class BaseWSGIServerNoBind(werkzeug.serving.BaseWSGIServer):
    """ werkzeug Base WSGI Server patched to skip socket binding. PreforkServer
    use this class, sets the socket and calls the process_request() manually
    """
    def __init__(self, app):
        werkzeug.serving.BaseWSGIServer.__init__(self, "1", "1", app)
    def server_bind(self):
        # we dont bind beause we use the listen socket of PreforkServer#socket
        # instead we close the socket
        if self.socket:
            self.socket.close()
    def server_activate(self):
        # dont listen as we use PreforkServer#socket
        pass

# _reexec() should set LISTEN_* to avoid connection refused during reload time. It
# should also work with systemd socket activation. This is currently untested
# and not yet used.

class ThreadedWSGIServerReloadable(werkzeug.serving.ThreadedWSGIServer):
    """ werkzeug Threaded WSGI Server patched to allow reusing a listen socket
    given by the environement, this is used by autoreload to keep the listen
    socket open when a reload happens.
    """
    def server_bind(self):
        envfd = os.environ.get('LISTEN_FDS')
        if envfd and os.environ.get('LISTEN_PID') == str(os.getpid()):
            self.reload_socket = True
            self.socket = socket.fromfd(int(envfd), socket.AF_INET, socket.SOCK_STREAM)
            # should we os.close(int(envfd)) ? it seem python duplicate the fd.
        else:
            self.reload_socket = False
            super(ThreadedWSGIServerReloadable, self).server_bind()

    def server_activate(self):
        if not self.reload_socket:
            super(ThreadedWSGIServerReloadable, self).server_activate()

#----------------------------------------------------------
# AutoReload watcher
#----------------------------------------------------------

class AutoReload(object):
    def __init__(self, server):
        self.server = server
        self.files = {}
        self.modules = {}
        import pyinotify
        class EventHandler(pyinotify.ProcessEvent):
            def __init__(self, autoreload):
                self.autoreload = autoreload

            def process_IN_CREATE(self, event):
                _logger.debug('File created: %s', event.pathname)
                self.autoreload.files[event.pathname] = 1

            def process_IN_MODIFY(self, event):
                _logger.debug('File modified: %s', event.pathname)
                self.autoreload.files[event.pathname] = 1

        self.wm = pyinotify.WatchManager()
        self.handler = EventHandler(self)
        self.notifier = pyinotify.Notifier(self.wm, self.handler, timeout=0)
        mask = pyinotify.IN_MODIFY | pyinotify.IN_CREATE  # IN_MOVED_FROM, IN_MOVED_TO ?
        for path in openerp.tools.config.options["addons_path"].split(','):
            _logger.info('Watching addons folder %s', path)
            self.wm.add_watch(path, mask, rec=True)

    def process_data(self, files):
        xml_files = [i for i in files if i.endswith('.xml')]
        addons_path = openerp.tools.config.options["addons_path"].split(',')
        for i in xml_files:
            for path in addons_path:
                if i.startswith(path):
                    # find out wich addons path the file belongs to
                    # and extract it's module name
                    right = i[len(path) + 1:].split('/')
                    if len(right) < 2:
                        continue
                    module = right[0]
                    self.modules[module]=1
        if self.modules:
            _logger.info('autoreload: xml change detected, autoreload activated')
            restart()

    def process_python(self, files):
        # process python changes
        py_files = [i for i in files if i.endswith('.py')]
        py_errors = []
        # TODO keep python errors until they are ok
        if py_files:
            for i in py_files:
                try:
                    source = open(i, 'rb').read() + '\n'
                    compile(source, i, 'exec')
                except SyntaxError:
                    py_errors.append(i)
            if py_errors:
                _logger.info('autoreload: python code change detected, errors found')
                for i in py_errors:
                    _logger.info('autoreload: SyntaxError %s',i)
            else:
                _logger.info('autoreload: python code updated, autoreload activated')
                restart()

    def check_thread(self):
        # Check if some files have been touched in the addons path.
        # If true, check if the touched file belongs to an installed module
        # in any of the database used in the registry manager.
        while 1:
            while self.notifier.check_events(1000):
                self.notifier.read_events()
                self.notifier.process_events()
            l = self.files.keys()
            self.files.clear()
            self.process_data(l)
            self.process_python(l)

    def run(self):
        t = threading.Thread(target=self.check_thread)
        t.setDaemon(True)
        t.start()
        _logger.info('AutoReload watcher running')

#----------------------------------------------------------
# Servers: Threaded, Gevented and Prefork
#----------------------------------------------------------

class CommonServer(object):
    def __init__(self, app):
        # TODO Change the xmlrpc_* options to http_*
        self.app = app
        # config
        self.interface = config['xmlrpc_interface'] or '0.0.0.0'
        self.port = config['xmlrpc_port']
        # runtime
        self.pid = os.getpid()

    def dumpstacks(self):
        """ Signal handler: dump a stack trace for each existing thread."""
        # code from http://stackoverflow.com/questions/132058/getting-stack-trace-from-a-running-python-application#answer-2569696
        # modified for python 2.5 compatibility
        threads_info = dict([(th.ident, {'name': th.name,
                                        'uid': getattr(th,'uid','n/a')})
                                    for th in threading.enumerate()])
        code = []
        for threadId, stack in sys._current_frames().items():
            thread_info = threads_info.get(threadId)
            code.append("\n# Thread: %s (id:%s) (uid:%s)" % \
                        (thread_info and thread_info['name'] or 'n/a',
                         threadId,
                         thread_info and thread_info['uid'] or 'n/a'))
            for filename, lineno, name, line in traceback.extract_stack(stack):
                code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
                if line:
                    code.append("  %s" % (line.strip()))
        _logger.info("\n".join(code))

    def close_socket(self, sock):
        """ Closes a socket instance cleanly
        :param sock: the network socket to close
        :type sock: socket.socket
        """
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except socket.error, e:
            # On OSX, socket shutdowns both sides if any side closes it
            # causing an error 57 'Socket is not connected' on shutdown
            # of the other side (or something), see
            # http://bugs.python.org/issue4397
            # note: stdlib fixed test, not behavior
            if e.errno != errno.ENOTCONN or platform.system() not in ['Darwin', 'Windows']:
                raise
        sock.close()

class ThreadedServer(CommonServer):
    def __init__(self, app):
        super(ThreadedServer, self).__init__(app)
        self.main_thread_id = threading.currentThread().ident
        # Variable keeping track of the number of calls to the signal handler defined
        # below. This variable is monitored by ``quit_on_signals()``.
        self.quit_signals_received = 0

        #self.socket = None
        self.httpd = None

    def signal_handler(self, sig, frame):
        if sig in [signal.SIGINT,signal.SIGTERM]:
            # shutdown on kill -INT or -TERM
            self.quit_signals_received += 1
            if self.quit_signals_received > 1:
                # logging.shutdown was already called at this point.
                sys.stderr.write("Forced shutdown.\n")
                os._exit(0)
        elif sig == signal.SIGHUP:
            # restart on kill -HUP
            openerp.phoenix = True
            self.quit_signals_received += 1
        elif sig == signal.SIGQUIT:
            # dump stacks on kill -3
            self.dumpstacks()

    def cron_thread(self, number):
        while True:
            time.sleep(SLEEP_INTERVAL + number) # Steve Reich timing style
            registries = openerp.modules.registry.RegistryManager.registries
            _logger.debug('cron%d polling for jobs', number)
            for db_name, registry in registries.items():
                while True and registry.ready:
                    acquired = openerp.addons.base.ir.ir_cron.ir_cron._acquire_job(db_name)
                    if not acquired:
                        break

    def cron_spawn(self):
        """ Start the above runner function in a daemon thread.

        The thread is a typical daemon thread: it will never quit and must be
        terminated when the main process exits - with no consequence (the processing
        threads it spawns are not marked daemon).

        """
        # Force call to strptime just before starting the cron thread
        # to prevent time.strptime AttributeError within the thread.
        # See: http://bugs.python.org/issue7980
        datetime.datetime.strptime('2012-01-01', '%Y-%m-%d')
        for i in range(openerp.tools.config['max_cron_threads']):
            def target():
                self.cron_thread(i)
            t = threading.Thread(target=target, name="openerp.service.cron.cron%d" % i)
            t.setDaemon(True)
            t.start()
            _logger.debug("cron%d started!" % i)

    def http_thread(self):
        def app(e,s):
            return self.app(e,s)
        self.httpd = ThreadedWSGIServerReloadable(self.interface, self.port, app)
        self.httpd.serve_forever()

    def http_spawn(self):
        threading.Thread(target=self.http_thread).start()
        _logger.info('HTTP service (werkzeug) running on %s:%s', self.interface, self.port)

    def start(self):
        _logger.debug("Setting signal handlers")
        if os.name == 'posix':
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            signal.signal(signal.SIGCHLD, self.signal_handler)
            signal.signal(signal.SIGHUP, self.signal_handler)
            signal.signal(signal.SIGQUIT, self.signal_handler)
        elif os.name == 'nt':
            import win32api
            win32api.SetConsoleCtrlHandler(lambda sig: signal_handler(sig, None), 1)
        self.cron_spawn()
        self.http_spawn()

    def stop(self):
        """ Shutdown the WSGI server. Wait for non deamon threads.
        """
        _logger.info("Initiating shutdown")
        _logger.info("Hit CTRL-C again or send a second signal to force the shutdown.")

        self.httpd.shutdown()
        self.close_socket(self.httpd.socket)

        # Manually join() all threads before calling sys.exit() to allow a second signal
        # to trigger _force_quit() in case some non-daemon threads won't exit cleanly.
        # threading.Thread.join() should not mask signals (at least in python 2.5).
        me = threading.currentThread()
        _logger.debug('current thread: %r', me)
        for thread in threading.enumerate():
            _logger.debug('process %r (%r)', thread, thread.isDaemon())
            if thread != me and not thread.isDaemon() and thread.ident != self.main_thread_id:
                while thread.isAlive():
                    _logger.debug('join and sleep')
                    # Need a busyloop here as thread.join() masks signals
                    # and would prevent the forced shutdown.
                    thread.join(0.05)
                    time.sleep(0.05)

        _logger.debug('--')
        openerp.modules.registry.RegistryManager.delete_all()
        logging.shutdown()

    def run(self):
        """ Start the http server and the cron thread then wait for a signal.

        The first SIGINT or SIGTERM signal will initiate a graceful shutdown while
        a second one if any will force an immediate exit.
        """
        self.start()

        # Wait for a first signal to be handled. (time.sleep will be interrupted
        # by the signal handler.) The try/except is for the win32 case.
        try:
            while self.quit_signals_received == 0:
                time.sleep(60)
        except KeyboardInterrupt:
            pass

        self.stop()

    def reload(self):
        os.kill(self.pid, signal.SIGHUP)

class GeventServer(CommonServer):
    def __init__(self, app):
        super(GeventServer, self).__init__(app)
        self.port = config['longpolling_port']
        self.httpd = None

    def watch_parent(self, beat=4):
        import gevent
        ppid = os.getppid()
        while True:
            if ppid != os.getppid():
                pid = os.getpid()
                _logger.info("LongPolling (%s) Parent changed", pid)
                # suicide !!
                os.kill(pid, signal.SIGTERM)
                return
            gevent.sleep(beat)

    def start(self):
        import gevent
        from gevent.wsgi import WSGIServer
        gevent.spawn(self.watch_parent)
        self.httpd = WSGIServer((self.interface, self.port), self.app)
        _logger.info('Evented Service (longpolling) running on %s:%s', self.interface, self.port)
        self.httpd.serve_forever()

    def stop(self):
        import gevent
        self.httpd.stop()
        gevent.shutdown()

    def run(self):
        self.start()
        self.stop()

class PreforkServer(CommonServer):
    """ Multiprocessing inspired by (g)unicorn.
    PreforkServer (aka Multicorn) currently uses accept(2) as dispatching
    method between workers but we plan to replace it by a more intelligent
    dispatcher to will parse the first HTTP request line.
    """
    def __init__(self, app):
        # config
        self.address = (config['xmlrpc_interface'] or '0.0.0.0', config['xmlrpc_port'])
        self.population = config['workers']
        self.timeout = config['limit_time_real']
        self.limit_request = config['limit_request']
        # working vars
        self.beat = 4
        self.app = app
        self.pid = os.getpid()
        self.socket = None
        self.workers_http = {}
        self.workers_cron = {}
        self.workers = {}
        self.generation = 0
        self.queue = []
        self.long_polling_pid = None

    def pipe_new(self):
        pipe = os.pipe()
        for fd in pipe:
            # non_blocking
            flags = fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK
            fcntl.fcntl(fd, fcntl.F_SETFL, flags)
            # close_on_exec
            flags = fcntl.fcntl(fd, fcntl.F_GETFD) | fcntl.FD_CLOEXEC
            fcntl.fcntl(fd, fcntl.F_SETFD, flags)
        return pipe

    def pipe_ping(self, pipe):
        try:
            os.write(pipe[1], '.')
        except IOError, e:
            if e.errno not in [errno.EAGAIN, errno.EINTR]:
                raise

    def signal_handler(self, sig, frame):
        if len(self.queue) < 5 or sig == signal.SIGCHLD:
            self.queue.append(sig)
            self.pipe_ping(self.pipe)
        else:
            _logger.warn("Dropping signal: %s", sig)

    def worker_spawn(self, klass, workers_registry):
        self.generation += 1
        worker = klass(self)
        pid = os.fork()
        if pid != 0:
            worker.pid = pid
            self.workers[pid] = worker
            workers_registry[pid] = worker
            return worker
        else:
            worker.run()
            sys.exit(0)

    def long_polling_spawn(self):
        nargs = stripped_sys_argv('--pidfile','--workers')
        cmd = nargs[0]
        cmd = os.path.join(os.path.dirname(cmd), "openerp-gevent")
        nargs[0] = cmd
        popen = subprocess.Popen(nargs)
        self.long_polling_pid = popen.pid

    def worker_pop(self, pid):
        if pid in self.workers:
            _logger.debug("Worker (%s) unregistered",pid)
            try:
                self.workers_http.pop(pid,None)
                self.workers_cron.pop(pid,None)
                u = self.workers.pop(pid)
                u.close()
            except OSError:
                return

    def worker_kill(self, pid, sig):
        try:
            os.kill(pid, sig)
        except OSError, e:
            if e.errno == errno.ESRCH:
                self.worker_pop(pid)

    def process_signals(self):
        while len(self.queue):
            sig = self.queue.pop(0)
            if sig in [signal.SIGINT,signal.SIGTERM]:
                raise KeyboardInterrupt
            elif sig == signal.SIGHUP:
                # restart on kill -HUP
                openerp.phoenix = True
                raise KeyboardInterrupt
            elif sig == signal.SIGQUIT:
                # dump stacks on kill -3
                self.dumpstacks()
            elif sig == signal.SIGTTIN:
                # increase number of workers
                self.population += 1
            elif sig == signal.SIGTTOU:
                # decrease number of workers
                self.population -= 1

    def process_zombie(self):
        # reap dead workers
        while 1:
            try:
                wpid, status = os.waitpid(-1, os.WNOHANG)
                if not wpid:
                    break
                if (status >> 8) == 3:
                    msg = "Critial worker error (%s)"
                    _logger.critical(msg, wpid)
                    raise Exception(msg % wpid)
                self.worker_pop(wpid)
            except OSError, e:
                if e.errno == errno.ECHILD:
                    break
                raise

    def process_timeout(self):
        now = time.time()
        for (pid, worker) in self.workers.items():
            if (worker.watchdog_timeout is not None) and \
                (now - worker.watchdog_time >= worker.watchdog_timeout):
                _logger.error("Worker (%s) timeout", pid)
                self.worker_kill(pid, signal.SIGKILL)

    def process_spawn(self):
        while len(self.workers_http) < self.population:
            self.worker_spawn(WorkerHTTP, self.workers_http)
        while len(self.workers_cron) < config['max_cron_threads']:
            self.worker_spawn(WorkerCron, self.workers_cron)
        if not self.long_polling_pid:
            self.long_polling_spawn()

    def sleep(self):
        try:
            # map of fd -> worker
            fds = dict([(w.watchdog_pipe[0],w) for k,w in self.workers.items()])
            fd_in = fds.keys() + [self.pipe[0]]
            # check for ping or internal wakeups
            ready = select.select(fd_in, [], [], self.beat)
            # update worker watchdogs
            for fd in ready[0]:
                if fd in fds:
                    fds[fd].watchdog_time = time.time()
                try:
                    # empty pipe
                    while os.read(fd, 1):
                        pass
                except OSError, e:
                    if e.errno not in [errno.EAGAIN]:
                        raise
        except select.error, e:
            if e[0] not in [errno.EINTR]:
                raise

    def start(self):
        # wakeup pipe, python doesnt throw EINTR when a syscall is interrupted
        # by a signal simulating a pseudo SA_RESTART. We write to a pipe in the
        # signal handler to overcome this behaviour
        self.pipe = self.pipe_new()
        # set signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGHUP, self.signal_handler)
        signal.signal(signal.SIGCHLD, self.signal_handler)
        signal.signal(signal.SIGQUIT, self.signal_handler)
        signal.signal(signal.SIGTTIN, self.signal_handler)
        signal.signal(signal.SIGTTOU, self.signal_handler)
        # listen to socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(0)
        self.socket.bind(self.address)
        self.socket.listen(8*self.population)

    def stop(self, graceful=True):
        if self.long_polling_pid is not None:
            self.worker_kill(self.long_polling_pid, signal.SIGKILL)     # FIXME make longpolling process handle SIGTERM correctly
            self.long_polling_pid = None
        if graceful:
            _logger.info("Stopping gracefully")
            limit = time.time() + self.timeout
            for pid in self.workers.keys():
                self.worker_kill(pid, signal.SIGTERM)
            while self.workers and time.time() < limit:
                self.process_zombie()
                time.sleep(0.1)
        else:
            _logger.info("Stopping forcefully")
        for pid in self.workers.keys():
            self.worker_kill(pid, signal.SIGTERM)
        self.socket.close()

    def run(self):
        self.start()
        _logger.debug("Multiprocess starting")
        while 1:
            try:
                #_logger.debug("Multiprocess beat (%s)",time.time())
                self.process_signals()
                self.process_zombie()
                self.process_timeout()
                self.process_spawn()
                self.sleep()
            except KeyboardInterrupt:
                _logger.debug("Multiprocess clean stop")
                self.stop()
                break
            except Exception,e:
                _logger.exception(e)
                self.stop(False)
                sys.exit(-1)

class Worker(object):
    """ Workers """
    def __init__(self, multi):
        self.multi = multi
        self.watchdog_time = time.time()
        self.watchdog_pipe = multi.pipe_new()
        # Can be set to None if no watchdog is desired.
        self.watchdog_timeout = multi.timeout
        self.ppid = os.getpid()
        self.pid = None
        self.alive = True
        # should we rename into lifetime ?
        self.request_max = multi.limit_request
        self.request_count = 0

    def setproctitle(self, title=""):
        setproctitle('openerp: %s %s %s' % (self.__class__.__name__, self.pid, title))

    def close(self):
        os.close(self.watchdog_pipe[0])
        os.close(self.watchdog_pipe[1])

    def signal_handler(self, sig, frame):
        self.alive = False

    def sleep(self):
        try:
            ret = select.select([self.multi.socket], [], [], self.multi.beat)
        except select.error, e:
            if e[0] not in [errno.EINTR]:
                raise

    def process_limit(self):
        # If our parent changed sucide
        if self.ppid != os.getppid():
            _logger.info("Worker (%s) Parent changed", self.pid)
            self.alive = False
        # check for lifetime
        if self.request_count >= self.request_max:
            _logger.info("Worker (%d) max request (%s) reached.", self.pid, self.request_count)
            self.alive = False
        # Reset the worker if it consumes too much memory (e.g. caused by a memory leak).
        rss, vms = psutil.Process(os.getpid()).get_memory_info()
        if vms > config['limit_memory_soft']:
            _logger.info('Worker (%d) virtual memory limit (%s) reached.', self.pid, vms)
            self.alive = False # Commit suicide after the request.

        # VMS and RLIMIT_AS are the same thing: virtual memory, a.k.a. address space
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (config['limit_memory_hard'], hard))

        # SIGXCPU (exceeded CPU time) signal handler will raise an exception.
        r = resource.getrusage(resource.RUSAGE_SELF)
        cpu_time = r.ru_utime + r.ru_stime
        def time_expired(n, stack):
            _logger.info('Worker (%d) CPU time limit (%s) reached.', config['limit_time_cpu'])
            # We dont suicide in such case
            raise Exception('CPU time limit exceeded.')
        signal.signal(signal.SIGXCPU, time_expired)
        soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_time + config['limit_time_cpu'], hard))

    def process_work(self):
        pass

    def start(self):
        self.pid = os.getpid()
        self.setproctitle()
        _logger.info("Worker %s (%s) alive", self.__class__.__name__, self.pid)
        # Reseed the random number generator
        random.seed()
        # Prevent fd inherientence close_on_exec
        flags = fcntl.fcntl(self.multi.socket, fcntl.F_GETFD) | fcntl.FD_CLOEXEC
        fcntl.fcntl(self.multi.socket, fcntl.F_SETFD, flags)
        # reset blocking status
        self.multi.socket.setblocking(0)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)

    def stop(self):
        pass

    def run(self):
        try:
            self.start()
            while self.alive:
                self.process_limit()
                self.multi.pipe_ping(self.watchdog_pipe)
                self.sleep()
                self.process_work()
            _logger.info("Worker (%s) exiting. request_count: %s.", self.pid, self.request_count)
            self.stop()
        except Exception,e:
            _logger.exception("Worker (%s) Exception occured, exiting..." % self.pid)
            # should we use 3 to abort everything ?
            sys.exit(1)

class WorkerHTTP(Worker):
    """ HTTP Request workers """
    def process_request(self, client, addr):
        client.setblocking(1)
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # Prevent fd inherientence close_on_exec
        flags = fcntl.fcntl(client, fcntl.F_GETFD) | fcntl.FD_CLOEXEC
        fcntl.fcntl(client, fcntl.F_SETFD, flags)
        # do request using BaseWSGIServerNoBind monkey patched with socket
        self.server.socket = client
        # tolerate broken pipe when the http client closes the socket before
        # receiving the full reply
        try:
            self.server.process_request(client,addr)
        except IOError, e:
            if e.errno != errno.EPIPE:
                raise
        self.request_count += 1

    def process_work(self):
        try:
            client, addr = self.multi.socket.accept()
            self.process_request(client, addr)
        except socket.error, e:
            if e[0] not in (errno.EAGAIN, errno.ECONNABORTED):
                raise

    def start(self):
        Worker.start(self)
        self.server = BaseWSGIServerNoBind(self.multi.app)

class WorkerCron(Worker):
    """ Cron workers """

    def __init__(self, multi):
        super(WorkerCron, self).__init__(multi)
        # process_work() below process a single database per call.
        # The variable db_index is keeping track of the next database to
        # process.
        self.db_index = 0

    def sleep(self):
        # Really sleep once all the databases have been processed.
        if self.db_index == 0:
            interval = SLEEP_INTERVAL + self.pid % 10 # chorus effect
            time.sleep(interval)

    def _db_list(self):
        if config['db_name']:
            db_names = config['db_name'].split(',')
        else:
            db_names = openerp.service.db.exp_list(True)
        return db_names

    def process_work(self):
        rpc_request = logging.getLogger('openerp.netsvc.rpc.request')
        rpc_request_flag = rpc_request.isEnabledFor(logging.DEBUG)
        _logger.debug("WorkerCron (%s) polling for jobs", self.pid)
        db_names = self._db_list()
        if len(db_names):
            self.db_index = (self.db_index + 1) % len(db_names)
            db_name = db_names[self.db_index]
            self.setproctitle(db_name)
            if rpc_request_flag:
                start_time = time.time()
                start_rss, start_vms = psutil.Process(os.getpid()).get_memory_info()
            
            import openerp.addons.base as base
            base.ir.ir_cron.ir_cron._acquire_job(db_name)
            openerp.modules.registry.RegistryManager.delete(db_name)

            # dont keep cursors in multi database mode
            if len(db_names) > 1:
                openerp.sql_db.close_db(db_name)
            if rpc_request_flag:
                end_time = time.time()
                end_rss, end_vms = psutil.Process(os.getpid()).get_memory_info()
                logline = '%s time:%.3fs mem: %sk -> %sk (diff: %sk)' % (db_name, end_time - start_time, start_vms / 1024, end_vms / 1024, (end_vms - start_vms)/1024)
                _logger.debug("WorkerCron (%s) %s", self.pid, logline)

            self.request_count += 1
            if self.request_count >= self.request_max and self.request_max < len(db_names):
                _logger.error("There are more dabatases to process than allowed "
                    "by the `limit_request` configuration variable: %s more.",
                    len(db_names) - self.request_max)
        else:
            self.db_index = 0

    def start(self):
        os.nice(10)     # mommy always told me to be nice with others...
        Worker.start(self)
        self.multi.socket.close()

#----------------------------------------------------------
# start/stop public api
#----------------------------------------------------------

server = None

def load_server_wide_modules():
    for m in openerp.conf.server_wide_modules:
        try:
            openerp.modules.module.load_openerp_module(m)
        except Exception:
            msg = ''
            if m == 'web':
                msg = """
The `web` module is provided by the addons found in the `openerp-web` project.
Maybe you forgot to add those addons in your addons_path configuration."""
            _logger.exception('Failed to load server-wide module `%s`.%s', m, msg)

def _reexec(updated_modules=None):
    """reexecute openerp-server process with (nearly) the same arguments"""
    if openerp.tools.osutil.is_running_as_nt_service():
        subprocess.call('net stop {0} && net start {0}'.format(nt_service_name), shell=True)
    exe = os.path.basename(sys.executable)
    args = stripped_sys_argv()
    args +=  ["-u", ','.join(updated_modules)]
    if not args or args[0] != exe:
        args.insert(0, exe)
    os.execv(sys.executable, args)

def start():
    """ Start the openerp http server and cron processor.
    """
    global server
    load_server_wide_modules()
    if config['workers']:
        server = PreforkServer(openerp.service.wsgi_server.application)
    elif openerp.evented:
        server = GeventServer(openerp.service.wsgi_server.application)
    else:
        server = ThreadedServer(openerp.service.wsgi_server.application)

    if config['auto_reload']:
        autoreload = AutoReload(server)
        autoreload.run()

    server.run()

    # like the legend of the phoenix, all ends with beginnings
    if getattr(openerp, 'phoenix', False):
        modules = []
        if config['auto_reload']:
            modules = autoreload.modules.keys()
        _reexec(modules)
    sys.exit(0)

def restart():
    """ Restart the server
    """
    if os.name == 'nt':
        # run in a thread to let the current thread return response to the caller.
        threading.Thread(target=_reexec).start()
    else:
        os.kill(server.pid, signal.SIGHUP)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
