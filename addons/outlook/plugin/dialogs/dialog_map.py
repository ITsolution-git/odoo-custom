 #!/usr/bin/python
 #-*- encoding: utf-8 -*-

from processors import *
from opt_processors import *
import sys
import os
import addin
from dialogs import ShowDialog, MakePropertyPage
import win32ui
import commctrl
import win32con
import win32gui
import win32gui_struct
import xmlrpclib
from manager import ustr
import chilkat

try:
    enumerate
except NameError:   # enumerate new in 2.3
    def enumerate(seq):
        return [(i, seq[i]) for i in xrange(len(seq))]

BIF_NEWDIALOGSTYLE = 0x00000040
BIF_NONEWFOLDERBUTTON = 0x0000200
CSIDL_COMMONMYPICTURES = 0x00000036

class _WIN32MASKEDSTRUCT:
    def __init__(self, **kw):
        full_fmt = ""
        for name, fmt, default, mask in self._struct_items_:
            self.__dict__[name] = None
            if fmt == "z":
                full_fmt += "pi"
            else:
                full_fmt += fmt
        for name, val in kw.iteritems():
            if name not in self.__dict__:
                raise ValueError("LVITEM structures do not have an item '%s'" % (name,))
            self.__dict__[name] = val

    def __setattr__(self, attr, val):
        if not attr.startswith("_") and attr not in self.__dict__:
            raise AttributeError(attr)
        self.__dict__[attr] = val

    def toparam(self):
        self._buffs = []
        full_fmt = ""
        vals = []
        mask = 0
        # calc the mask
        for name, fmt, default, this_mask in self._struct_items_:
            if this_mask is not None and self.__dict__.get(name) is not None:
                mask |= this_mask
        self.mask = mask
        for name, fmt, default, this_mask in self._struct_items_:
            val = self.__dict__[name]
            if fmt == "z":
                fmt = "Pi"
                if val is None:
                    vals.append(0)
                    vals.append(0)
                else:
                    # Note this demo still works with byte strings.  An
                    # alternate strategy would be to use unicode natively
                    # and use the 'W' version of the messages - eg,
                    # LVM_SETITEMW etc.
                    val = val + "\0"
                    if isinstance(val, unicode):
                        val = val.encode("mbcs")
                    str_buf = array.array("b", val)
                    vals.append(str_buf.buffer_info()[0])
                    vals.append(len(val))
                    self._buffs.append(str_buf) # keep alive during the call.
            else:
                if val is None:
                    val = default
                vals.append(val)
            full_fmt += fmt
        return struct.pack(*(full_fmt,) + tuple(vals))


# NOTE: See the win32gui_struct module for an alternative way of dealing
# with these structures
class LVITEM(_WIN32MASKEDSTRUCT):
    _struct_items_ = [
        ("mask", "I", 0, None),
        ("iItem", "i", 0, None),
        ("iSubItem", "i", 0, None),
        ("state", "I", 0, commctrl.LVIF_STATE),
        ("stateMask", "I", 0, None),
        ("text", "z", None, commctrl.LVIF_TEXT),
        ("iImage", "i", 0, commctrl.LVIF_IMAGE),
        ("lParam", "i", 0, commctrl.LVIF_PARAM),
        ("iIdent", "i", 0, None),
        ("cchTextMax", "i", 0, 255),
        ("pszText", "i", 0, None),
        ("flags", "i", 0, None),
    ]

class LVCOLUMN(_WIN32MASKEDSTRUCT):
    _struct_items_ = [
        ("mask", "I", 0, None),
        ("fmt", "i", 0, commctrl.LVCF_FMT),
        ("cx", "i", 0, commctrl.LVCF_WIDTH),
        ("text", "z", None, commctrl.LVCF_TEXT),
        ("iSubItem", "i", 0, commctrl.LVCF_SUBITEM),
        ("iImage", "i", 0, commctrl.LVCF_IMAGE),
        ("iOrder", "i", 0, commctrl.LVCF_ORDER),
    ]

global flag_stop
flag_stop=win32con.MB_ICONSTOP

global flag_error
flag_error=win32con.MB_ICONERROR

global flag_info
flag_info=win32con.MB_ICONINFORMATION

global flag_excl
flag_excl=win32con.MB_ICONEXCLAMATION

#global NewConn
NewConn=addin.GetConn()
## Retrieves current registered XMLRPC connection
def GetConn():
    return NewConn

global objects_with_match
objects_with_match=[]

global hwndChk_list
hwndChk_list=[]

global search_text
search_text='search_text'

global name
name=''
global email
email=''

def check():
    server = NewConn.getitem('_server')
    port = NewConn.getitem('_port')
    NewConn.GetDBList()
    if str(NewConn.getitem('_running')) == 'False':
        win32ui.MessageBox("No server running on host "+ server+" at port "+str(port), "Server Connection", flag_excl)
        return False
    if str(NewConn.getitem('_login')) == 'False':
        win32ui.MessageBox("Please login to the database first", "Database Connection", flag_excl)
        return False
    return True
def resetConnAttribs(window):
    config = window.manager.LoadConfig()
    NewConn.setitem('_server', config['server'])
    NewConn.setitem('_port', config['port'])
    NewConn.setitem('protocol', config['protocol'])
    NewConn.setitem('_uri', "http://" + config['server'] + ":" + str(config['port']))
    NewConn.setitem('_obj_list', config['objects'])
    NewConn.setitem('_dbname', config['database'])
    NewConn.setitem('_uname', config['uname'])
    NewConn.setitem('_pwd', config['pwd'])
    NewConn.setitem('_login', str(config['login']))
    return

def setConnAttribs(server, port, manager):
    protocol = NewConn.getitem('protocol')
    if protocol=='XML-RPCS':
        protocol='https://'
    else:
        protocol='http://'
    uri = protocol + server + ":" + str(port)
    NewConn.setitem('_server',server)
    NewConn.setitem('_port',port)
    NewConn.setitem('_uri',uri)
    NewConn.GetDBList()
    manager.config = manager.LoadConfig()
    NewConn.setitem('_dbname',manager.config['database'])
    NewConn.setitem('_uname', manager.config['uname'])
    NewConn.setitem('_pwd', manager.config['pwd'])
    NewConn.setitem('_login', str(manager.config['login']))
    NewConn.setitem('_obj_list', manager.config['objects'])
    return

def getConnAttributes(manager):
    manager.config['server'] = NewConn.getitem('_server')
    manager.config['port'] = NewConn.getitem('_port')
    manager.config['protocol'] = NewConn.getitem('protocol')
    manager.config['objects'] = eval(NewConn.getitem('_obj_list'))
    manager.config['database'] = NewConn.getitem('_dbname')
    manager.config['uname'] = NewConn.getitem('_uname')
    manager.config['pwd'] = NewConn.getitem('_pwd')
    manager.config['login'] = NewConn.getitem('_login')
    return

def getMessage(e):
    import pywintypes
    print "Exception %s: %s"%(type(e),str(e))
    msg = str(e)
    if type(e) == pywintypes.com_error:
        msg=str(e)
    elif type(e) == xmlrpclib.Fault:
        msg = str(e.faultCode) or e.faultString or e.message or str(e)
    else:
        if hasattr(e, 'faultCode') and e.faultCode:
            msg = str(e.faultCode)
        elif hasattr(e, 'faultString') and e.faultString:
            msg = e.faultString
        elif hasattr(e, 'message') and e.message:
            msg = e.message
    return msg

class OKButtonProcessor(ButtonProcessor):
    def __init__(self, window, control_ids):
        self.mngr = window.manager
        ControlProcessor.__init__(self, window, control_ids)

    def OnClicked(self, id):
        server = win32gui.GetDlgItemText(self.window.hwnd, self.other_ids[0])
        try:
            port = int(win32gui.GetDlgItemText(self.window.hwnd, self.other_ids[1]))
        except ValueError, e:
            print "Exception : %s"%str(e)
            win32ui.MessageBox("Port should be an integer", "Error", flag_excl)
            return
        except Exception,e:
            msg = getMessage(e)
            win32ui.MessageBox(msg, "Error", flag_excl)
            return
        setConnAttribs(server, port, self.mngr)
        if str(NewConn.getitem('_running')) == 'False':
        	msg = "No server running on host '%s' at port '%d'. Press ignore to still continue with this configuration?"%(server,port)
         	r=win32ui.MessageBox(msg, "Server Connection", win32con.MB_ABORTRETRYIGNORE | win32con.MB_ICONQUESTION)
         	if r==3:
				resetConnAttribs(self.window)
				return
         	elif r==4:
         	 	self.OnClicked(id)
         	elif r==5:
         		setConnAttribs(server, port, self.mngr)
        win32gui.EndDialog(self.window.hwnd, id)

class DoneButtonProcessor(ButtonProcessor):
    def OnClicked(self, id):
        getConnAttributes(self.window.manager)
        self.window.manager.SaveConfig()
        win32gui.EndDialog(self.window.hwnd, id)

class MessageProcessor(ControlProcessor):
    def Init(self):
        text = "This Outlook Plugin for OpenERP s.a. has been developed by TinyERP \n\n \
                For more information, please visit our website \n \
                 http://www.openerp.com \n\n \
                Contact Us :\n \
                sales@openerp.com \n\n \
                2001-TODAY OpenERP s.a.. All rights reserved. \n"
        win32gui.SendMessage(self.GetControl(), win32con.WM_SETTEXT, 0, text)

    def GetPopupHelpText(self, cid):
        return "Displays details on this plugin"

class TabProcessor(ControlProcessor):
    def __init__(self, window, control_ids, page_ids):
        ControlProcessor.__init__(self, window, control_ids)
        self.page_ids = page_ids.split()

    def Init(self):
        self.pages = {}
        self.currentPage = None
        self.currentPageIndex = -1
        self.currentPageHwnd = None
        for index, page_id in enumerate(self.page_ids):
            template = self.window.manager.dialog_parser.dialogs[page_id]
            self.addPage(index, page_id, template[0][0])
        server = self.window.manager.config['server']
        port = self.window.manager.config['port']
        setConnAttribs(server, port, self.window.manager)
        self.switchToPage(0)

    def Done(self):
        if self.currentPageHwnd is not None:
            if not self.currentPage.SaveAllControls():
                win32gui.SendMessage(self.GetControl(), commctrl.TCM_SETCURSEL, self.currentPageIndex,0)
                return False
        return True

    def OnNotify(self, nmhdr, wparam, lparam):
        selChangedCode =  5177342
        code = nmhdr[2]
        if code==selChangedCode:
            index = win32gui.SendMessage(self.GetControl(), commctrl.TCM_GETCURSEL, 0,0)
            if index!=self.currentPageIndex:
                self.switchToPage(index)

    def switchToPage(self, index):
        if self.currentPageHwnd is not None:
            if not self.currentPage.SaveAllControls():
                win32gui.SendMessage(self.GetControl(), commctrl.TCM_SETCURSEL, self.currentPageIndex,0)
                return 1
            win32gui.DestroyWindow(self.currentPageHwnd)
        self.currentPage = MakePropertyPage(self.GetControl(), self.window.manager, self.window.config, self.pages[index])
        self.currentPageHwnd = self.currentPage.CreateWindow()
        self.currentPageIndex = index
        return 0
#
    def addPage(self, item, idName, label):
        format = "iiiiiii"
        lbuf = win32gui.PyMakeBuffer(len(label)+1)
        address,l = win32gui.PyGetBufferAddressAndLen(lbuf)
        win32gui.PySetString(address, label)

        buf = struct.pack(format,
            commctrl.TCIF_TEXT, # mask
            0, # state
            0, # state mask
            address,
            0, #unused
            0, #image
            item
            )
        item = win32gui.SendMessage(self.GetControl(),
                             commctrl.TCM_INSERTITEM,
                             item,
                             buf)
        self.pages[item] = idName

class DialogCommand(ButtonProcessor):
    def __init__(self, window, control_ids, idd, func=None, args=()):
        self.idd = idd
        self.func = func
        self.args = args
        ButtonProcessor.__init__(self, window, control_ids)

    def OnClicked(self, id):
        self.id = id
        if self.func:
            args = (self, ) + self.args
            self.func(*args)
        parent = self.window.hwnd
        self.window.SaveAllControls()
        ShowDialog(parent, self.window.manager, self.window.config, self.idd)
        self.window.LoadAllControls()

    def GetPopupHelpText(self, id):
        dd = self.window.manager.dialog_parser.dialogs[self.idd]
        return "Displays the %s dialog" % dd.caption

def ReloadAllControls(btnProcessor,*args):
    server = NewConn.getitem('_server')
    port = NewConn.getitem('_port')
    btnProcessor.window.LoadAllControls()
    if str(NewConn.getitem('_running')) == 'False':
        win32ui.MessageBox("No server running on host "+ server+" at port "+str(port), "Server Connection", flag_excl)
    return

def TestConnection(btnProcessor,*args):
    server = NewConn.getitem('_server')
    port = NewConn.getitem('_port')
    url = NewConn.getitem('_uri')
    NewConn.GetDBList()
    if str(NewConn.getitem('_running')) == 'False':
        btnProcessor.window.LoadAllControls()
        win32ui.MessageBox("No server running on host "+ server+" at port "+str(port), "OpenERP Connection", flag_excl)
        return
    try:
        dbname = win32gui.GetDlgItemText(btnProcessor.window.hwnd, 7000)
        if not dbname:
            win32ui.MessageBox("Authentication Error !\nBad Database Name !", "OpenERP Connection", flag_excl)
            return
    except Exception,e:
        print "Exception %s: %s"%(type(e),str(e))
    dbname = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
    if not dbname:
        win32ui.MessageBox("No database found on host "+ server+" at port "+str(port), "OpenERP Connection", flag_excl)
        return

    uname = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[1])
    pwd = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[2])

    if not uname:
        win32ui.MessageBox("Authentication Error !\nBad User Name !", "OpenERP Connection", flag_excl)
        return
    if not pwd:
        win32ui.MessageBox("Authentication Error !\nBad Password !", "OpenERP Connection", flag_excl)
        return

    #Establish Connection
    try:
        uid = NewConn.login(dbname, uname, pwd)
        if uid:
            msg = "Connection Successful"
            NewConn.setitem('_login', 'True')
            NewConn.setitem('_uname', uname)
            NewConn.setitem('_pwd', pwd)
            NewConn.setitem('_uid', uid)
            flag = flag_info
            if not NewConn.IsCRMInstalled():
                msg+= '\n\n'+" 'CRM' module is not installed. So CRM cases cannot be created."
                NewConn.setitem('_iscrm', 'False')
            else:
                NewConn.setitem('_iscrm', 'True')
        else:
            msg = "Authentication Error !\nBad UserName or Password"
            flag = flag_stop
            NewConn.setitem('_login', 'False')
    except Exception,e:
        msg = "Authentication Error !\n\n" + getMessage(e)
        flag = flag_error
    win32ui.MessageBox(msg, "OpenERP Connection", flag)
    return

def BrowseCallbackProc(hwnd, msg, lp, data):
    from win32com.shell import shell, shellcon
    if msg== shellcon.BFFM_INITIALIZED:
        win32gui.SendMessage(hwnd, shellcon.BFFM_SETSELECTION, 1, data)
        win32gui.SendMessage(hwnd, shellcon.BFFM_ENABLEOK, 0, 0)
    elif msg == shellcon.BFFM_SELCHANGED:
        # Set the status text of the
        # For this message, 'lp' is the address of the PIDL.
        pidl = shell.AddressAsPIDL(lp)
        try:
            path = shell.SHGetPathFromIDList(pidl)
            if os.path.isdir(path):
                win32gui.SendMessage(hwnd, shellcon.BFFM_ENABLEOK, 0, 0)
            else:
                ext = path.split('.')[-1]
                if ext not in ['gif', 'bmp', 'jpg', 'tif', 'ico', 'png']:
                        win32gui.SendMessage(hwnd, shellcon.BFFM_ENABLEOK, 0, 0)

                else:
                    win32gui.SendMessage(hwnd, shellcon.BFFM_ENABLEOK, 0, 1)
        except shell.error:
            # No path for this PIDL
            pass

def GetImagePath(btnProcessor,*args):
    from win32com.shell import shell, shellcon
    ulFlags = shellcon.BIF_BROWSEINCLUDEFILES | BIF_NEWDIALOGSTYLE | BIF_NONEWFOLDERBUTTON
    pidl, display_name, image_list=shell.SHBrowseForFolder(btnProcessor.window.hwnd, # parent HWND
                            None, # root PIDL.
                            "Get the image path", # title
                            ulFlags, # flags
                            BrowseCallbackProc, # callback function
                            os.getcwd() # 'data' param for the callback
                            )
    if (pidl, display_name, image_list) == (None, None, None):
      return
    else:
      path = shell.SHGetPathFromIDList (pidl)
      win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0], path)

def AddNewObject(btnProcessor,*args):
    #Check if server running or user logged in
    b = check()
    if not b:
        return

    #Check if title or object not specified
    obj_title = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
    obj_name = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[1])
    if not obj_title:
        win32ui.MessageBox("No Title specified", "Documents Setting", flag_excl)
        return
    if not obj_name:
        win32ui.MessageBox("No Document specified", "Documents Setting", flag_excl)
        return

    #Check if object does not exist in the database or it already exist in the list
    try:
        all_obj_list = NewConn.GetAllObjects()
        curr_obj_list = [obj[1] for obj in NewConn.GetObjList()]
        curr_title_list = [obj[0] for obj in NewConn.GetObjList()]
        if obj_name not in all_obj_list:
            win32ui.MessageBox("No such Document exists", "Documents Setting", flag_excl)
            return
        elif obj_name in curr_obj_list:
            win32ui.MessageBox("Document already in the list", "Documents Setting", flag_info)
            return
        elif obj_title in curr_title_list:
            win32ui.MessageBox("Title already in the list. Please give different title", "Documents Setting", flag_excl)
            return

        #extract image path and load the image
        image_path=''
        image_path = os.path.join(btnProcessor.window.manager.application_directory, "dialogs\\resources\\openerp_logo1.bmp")
        path=win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[2])
        if path:
            image_path = path
        load_bmp_flags=win32con.LR_LOADFROMFILE | win32con.LR_LOADTRANSPARENT
        try:
            hicon = win32gui.LoadImage(0, image_path,win32con.IMAGE_BITMAP, 40, 40, load_bmp_flags)
        except Exception,e:
            msg=getMessage(e)
            hicon=None
            win32ui.MessageBox(msg, "Load Image", flag_error)

        #Add the object in the list
        win32gui.ImageList_Add(il,hicon,0)
        cnt = win32gui.ImageList_GetImageCount(il)

        hwndList = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[3])
        num_items = win32gui.SendMessage(hwndList, commctrl.LVM_GETITEMCOUNT)

        item = LVITEM(text=obj_title, iImage=cnt-2, iItem = num_items)
        new_index = win32gui.SendMessage(hwndList, commctrl.LVM_INSERTITEM, 0, item.toparam())

        win32gui.SendMessage(hwndList, commctrl.LVM_SETIMAGELIST, commctrl.LVSIL_SMALL, il)

        item = LVITEM(text=obj_name, iItem = new_index, iSubItem = 1)
        win32gui.SendMessage(hwndList, commctrl.LVM_SETITEM, 0, item.toparam())

        NewConn.InsertObj(obj_title,obj_name,image_path)
    except Exception, e:
        msg = "Document not added\n\n" + getMessage(e)
        win32ui.MessageBox(msg,"Documents Setting",flag_excl)
        return

    #Empty all the text controls
    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0], '')
    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[1], '')
    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[2], '')

def DeleteSelectedObjects(btnProcessor,*args):
    #Check if server running or user logged in
    b = check()
    if not b:
        return

    #Delete selected items
    hwndList = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
    sel_count = win32gui.SendMessage(hwndList, commctrl.LVM_GETSELECTEDCOUNT)
    for i in range(0,sel_count):
        sel = win32gui.SendMessage(hwndList, commctrl.LVM_GETNEXTITEM, -1, commctrl.LVNI_SELECTED)
        buf,extra = win32gui_struct.EmptyLVITEM(1, 0)
        r = win32gui.SendMessage(hwndList, commctrl.LVM_GETITEMTEXT, sel, buf)
        sel_text = ''
        for n in extra:
            nombre = n.tostring()
            sel_text = nombre[0:r]
        s = win32gui.SendMessage(hwndList, commctrl.LVM_DELETEITEM, sel)
        try:
            NewConn.DeleteObject(sel_text)
        except Exception,e:
            msg = "Documents '%s' not deleted\n\n"%sel_text + getMessage(e)
            win32ui.MessageBox(msg,"Documents Setting",flag_excl)

def GetMail(processor):
    ex = processor.window.manager.outlook.ActiveExplorer()
    assert ex.Selection.Count == 1
    mail = ex.Selection.Item(1)
    return mail
#get selected records from list
def GetSelectedItems(hwndList):
    r=[]
    sel_count = win32gui.SendMessage(hwndList, commctrl.LVM_GETSELECTEDCOUNT)
    sel=-1
    for i in range(0,sel_count):
        sel = win32gui.SendMessage(hwndList, commctrl.LVM_GETNEXTITEM, sel, commctrl.LVNI_SELECTED)
        buf,extra = win32gui_struct.EmptyLVITEM(1, 0)
        size = win32gui.SendMessage(hwndList, commctrl.LVM_GETITEMTEXT, sel, buf)
        sel_text = ''
        for n in extra:
            nombre = n.tostring()
            sel_text = nombre[0:size]
        for item in objects_with_match:
            if item[2] == sel_text:
                 r.append(item)
    return r

def MakeAttachment(btnProcessor,*args):
    #Check if server running or user logged in
    b = check()
    if not b:
        return
    ex = btnProcessor.window.manager.outlook.ActiveExplorer()
    assert ex.Selection.Count == 1
    mail = ex.Selection.Item(1)
    mail = GetMail(btnProcessor)

    #get selected records
    hwndList = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
    r = GetSelectedItems(hwndList)
    if not r:
        win32ui.MessageBox("No records selected", "Make Attachment", flag_info)
        return
    try:
        flg = NewConn.ArchiveToOpenERP(r,mail)
        if flg:
            win32gui.EndDialog(btnProcessor.window.hwnd, btnProcessor.other_ids[1])
            return
    except Exception,e:
        msg = "Attachment not created \n\n" + getMessage(e)
        flag = flag_error
        win32ui.MessageBox(msg, "Make Attachment", flag)
    return

def CreateCase(btnProcessor,*args):
    try:
        #Check if server running or user logged in
        b = check()
        if not b:
            return

        if str(NewConn.getitem('_iscrm')) == 'True':
        #    Get the selected mail
            ex = btnProcessor.window.manager.outlook.ActiveExplorer()
            assert ex.Selection.Count == 1
            mail = ex.Selection.Item(1)
            section = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
            section = str(section)
            section=section.lower().replace(' ','.')
            if not section:
                win32ui.MessageBox("Documents can not be created.", "Documents Setting", flag_excl)
                return

            hwndList = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[1])
            partner_ids=[]
            r = GetSelectedItems(hwndList)
            for rec in r:
                if rec[0] == 'res.partner':
                    partner_ids.append(rec[1])

            #Create new case
            try:
                with_attachments=True
                if  mail.Attachments.Count > 0:
                    msg="The mail contains attachments. Do you want to create case with attachments?"
                    r=win32ui.MessageBox(msg, "Create Case", win32con.MB_YESNOCANCEL | win32con.MB_ICONQUESTION)
                    if r == 2:
                        return
                    elif r == 7:
                       with_attachments=False

                NewConn.CreateCase(str(section), mail, partner_ids, with_attachments)
                msg="New Document created."
                flag=flag_info
            except Exception,e:
                msg="New Document not created \n\n"+str(e)
                flag=flag_error
            win32ui.MessageBox(msg, "Create Document", flag)
            return
        else:
            win32ui.MessageBox("Document can not be created. CRM not installed", "Create Object", flag_info)
    except Exception, e:
        win32ui.MessageBox(str(e), 'New Document')

def GetSearchText(txtProcessor,*args):
    #Check if server running or user logged in
    b = check()
    if not b:
        return

    search_box = txtProcessor.GetControl()
    global search_text
    if txtProcessor.init_done:
        win32gui.SendMessage(search_box, win32con.WM_SETTEXT, 0,search_text)
        return

    # Get the selected mail and set the default value for search_text_control to mail.SenderEmailAddress
    ex = txtProcessor.window.manager.outlook.ActiveExplorer()
    assert ex.Selection.Count == 1
    mail = ex.Selection.Item(1)
    try:
        search_text = ustr(mail.SenderEmailAddress).encode('iso-8859-1')
    except Exception,e:
        pass
    win32gui.SendMessage(search_box, win32con.WM_SETTEXT, 0, search_text)
    txtProcessor.init_done=True

def SetNameColumn(listProcessor,*args):
    hwndList = listProcessor.GetControl()
    child_ex_style = win32gui.SendMessage(hwndList, commctrl.LVM_GETEXTENDEDLISTVIEWSTYLE, 0, 0)
    child_ex_style |= commctrl.LVS_EX_FULLROWSELECT
    win32gui.SendMessage(hwndList, commctrl.LVM_SETEXTENDEDLISTVIEWSTYLE, 0, child_ex_style)

    # set header row
    lvc =  LVCOLUMN(
                    mask = commctrl.LVCF_FMT | commctrl.LVCF_WIDTH | \
                    commctrl.LVCF_TEXT | commctrl.LVCF_SUBITEM
                    )
    lvc.fmt = commctrl.LVCFMT_LEFT
    lvc.iSubItem = 1
    lvc.text = "Document Type"
    lvc.cx = 100
    win32gui.SendMessage(hwndList, commctrl.LVM_INSERTCOLUMN, 0, lvc.toparam())
    lvc.iSubItem = 0
    lvc.text = "Name"
    lvc.cx = 240
    win32gui.SendMessage(hwndList, commctrl.LVM_INSERTCOLUMN, 0, lvc.toparam())
    listProcessor.init_done = True

def setList(list_hwnd):
    # Set default list of objects
    win32gui.SendMessage(list_hwnd, commctrl.LVM_DELETEALLITEMS)
    for obj in objects_with_match:
        num_items = win32gui.SendMessage(list_hwnd, commctrl.LVM_GETITEMCOUNT)
        item = LVITEM(text=obj[2],iItem = num_items)
        new = win32gui.SendMessage(list_hwnd, commctrl.LVM_INSERTITEM, 0, item.toparam())
        item = LVITEM(text=obj[3],iItem = new,  iSubItem = 1)
        win32gui.SendMessage(list_hwnd, commctrl.LVM_SETITEM, 0, item.toparam())

def SearchObjectsForText(btnProcessor,*args):
    #Check if server running or user logged in
    b = check()
    if not b:
        return

    search_txt = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
    if not search_txt:
        win32ui.MessageBox("Enter text to search for", "", flag_info)
        return
    # Get titles from list
    obj_titles=[]
    for ch in hwndChk_list:
        id = ch[0]
        hwnd = ch[1]
        chk = win32gui.SendMessage(hwnd, win32con.BM_GETCHECK)
        if chk:
            txt = win32gui.GetDlgItemText(btnProcessor.window.hwnd,id)
            obj_titles.append(txt)

    # Prepare list of objects to search for the seach_keyword
    obj_list = btnProcessor.window.manager.config['objects']
    search_list = []
    try:
        all_obj_list = NewConn.GetAllObjects()
        for title in obj_titles:
            objname = [obj[1] for obj in obj_list if obj[0] == title]
            if objname:
                assert len(objname) == 1
                if objname[0] in all_obj_list:
                     search_list.append(objname[0])
                else:
                    win32ui.MessageBox("Module %s (%s) not installed. Please install it." \
                                       %(title,objname[0]), "Archive to OpenERP", flag_excl)
                    return

        #  Get the records by searching the objects in search_list for the search_keyword as objects_with_match
        global objects_with_match
        list_hwnd = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[1])
        if search_list:
            objects_with_match = NewConn.GetObjectItems(search_list, search_txt)
            if not objects_with_match:
                win32ui.MessageBox("No matching records found in checked objects", "Archive to OpenERP", flag_info)
        else:
            win32ui.MessageBox("No object selected", "Archive to OpenERP", flag_info)
            objects_with_match=[]
        # Display the objects_with_match records in list
        setList(list_hwnd)
    except Exception,e:
        msg=getMessage(e)
        win32ui.MessageBox(msg, "Search Text", flag_error)

def CreateContact(btnProcessor,*args):
    b = check()
    if not b:
        return

    partner = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[9])
    combo = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[9])
    sel = win32gui.SendMessage(combo, win32con.CB_GETCURSEL)
    state_combo = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[10])
    state_sel = win32gui.SendMessage(state_combo, win32con.CB_GETCURSEL)
    coun_combo = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[11])
    country_sel = win32gui.SendMessage(coun_combo, win32con.CB_GETCURSEL)
    name = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
    email = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[1])
    office_no = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[2])
    mobile_no = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[3])
    fax = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[4])
    street = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[5])
    street2 = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[6])
    city = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[7])
    zip = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[8])
    if not name:
        win32ui.MessageBox("Please enter name.", "Create Contact", flag_stop)
        return

    res = {
           'name':ustr(name),
           'email':ustr(email),
           'phone':ustr(office_no),
           'mobile':ustr(mobile_no),
           'fax':ustr(fax),
           'street':ustr(street),
           'street2':ustr(street2),
           'city':ustr(city),
           'zip':ustr(zip)
       }

    fs_id = c_id = -1
    if not state_sel == -1 :
        try:
            temp = NewConn.GetAllState()
            i = -1
            for t in temp:
                i+=1
                if i == state_sel:
                    fs_id = t[0]
                    break;
            res ['state_id'] = fs_id
        except Exception, e:
            msg = getMessage(e)
            win32ui.MessageBox(msg, "New Partner", flag_error)
            pass
    if not country_sel == -1 :
        try:
            temp = NewConn.GetAllCountry()
            i = -1
            for t in temp:
                i+=1
                if i == country_sel:
                    c_id = t[0]
                    break;
            res ['country_id'] = c_id
        except Exception, e:
            msg = getMessage(e)
            win32ui.MessageBox(msg, "Open Contact", flag_error)
            pass
    try:
        id = NewConn.CreateContact(sel, str(res))
        if not partner:
            msg="New contact created."
        else:
            msg="New contact created for partner '%s'."%partner
    except Exception,e:
        msg="Contact not created \n\n" + getMessage(e)
        win32ui.MessageBox(msg, "Create Contact", flag_error)
        return
    win32ui.MessageBox(msg, "Create Contact", flag_info)
    for i in range(0,9):
        win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[i], '')
    win32gui.SendMessage(combo, win32con.CB_SETCURSEL, -1 )
    win32gui.SendMessage(state_combo, win32con.CB_SETCURSEL, -1 )
    win32gui.SendMessage(coun_combo, win32con.CB_SETCURSEL, -1 )

def SetAllText(txtProcessor,*args):
    # Set values for url, uname, pwd from config file
    url = NewConn.getitem('_uri')
    tbox = txtProcessor.GetControl()
    win32gui.SendMessage(tbox, win32con.WM_SETTEXT, 0, str(url))
    k=win32gui.GetDlgItemText(txtProcessor.window.hwnd, txtProcessor.control_id)
    uname = NewConn.getitem('_uname')
    tbox = txtProcessor.GetControl(txtProcessor.other_ids[0])
    win32gui.SendMessage(tbox, win32con.WM_SETTEXT, 0, str(uname))

def SetDefaultList(listProcessor,*args):
    import win32api
    hwndList = listProcessor.GetControl()

    # set full row select style
    child_ex_style = win32gui.SendMessage(hwndList, commctrl.LVM_GETEXTENDEDLISTVIEWSTYLE, 0, 0)
    child_ex_style |= commctrl.LVS_EX_FULLROWSELECT
    win32gui.SendMessage(hwndList, commctrl.LVM_SETEXTENDEDLISTVIEWSTYLE, 0, child_ex_style)

    # set header row
    lvc =  LVCOLUMN(
                    mask = commctrl.LVCF_FMT | commctrl.LVCF_WIDTH | \
                    commctrl.LVCF_TEXT | commctrl.LVCF_SUBITEM
                    )
    lvc.fmt = commctrl.LVCFMT_LEFT
    lvc.iSubItem = 1
    lvc.text = "Object Name"
    lvc.cx = 315
    win32gui.SendMessage(hwndList, commctrl.LVM_INSERTCOLUMN, 0, lvc.toparam())
    lvc.iSubItem = 0
    lvc.text = "Document Title"
    lvc.cx = 315
    win32gui.SendMessage(hwndList, commctrl.LVM_INSERTCOLUMN, 0, lvc.toparam())

    #create imagelist
    global il
    il = win32gui.ImageList_Create(
                        win32api.GetSystemMetrics(win32con.SM_CXSMICON),
                        win32api.GetSystemMetrics(win32con.SM_CYSMICON),
                        commctrl.ILC_COLOR32 | commctrl.ILC_MASK,
                        1, # initial size
                        0) # cGrow

    win32gui.SendMessage(hwndList, commctrl.LVM_SETIMAGELIST,\
                                 commctrl.LVSIL_SMALL, il)
    # Set objects from config
    objs = eval(NewConn.getitem('_obj_list'))
    load_bmp_flags=win32con.LR_LOADFROMFILE | win32con.LR_LOADTRANSPARENT
    for obj in objs:
        image_path = os.path.join(listProcessor.window.manager.application_directory, "dialogs\\resources\\openerp_logo1.bmp")
        path=obj[2]
        if path:
            image_path = path
        try:
            hicon = win32gui.LoadImage(0, image_path,win32con.IMAGE_BITMAP, 40, 40, load_bmp_flags)
        except Exception, e:
            msg = "Problem loading the image \n\n" + getMessage(e)
            hicon = None
            win32ui.MessageBox(msg, "Load Image", flag_error)

        #Add the object in the list
        win32gui.ImageList_Add(il,hicon,0)
        cnt = win32gui.ImageList_GetImageCount(il)
        num_items = win32gui.SendMessage(hwndList, commctrl.LVM_GETITEMCOUNT)
        item = LVITEM(text=obj[0],iImage=cnt-2, iItem = num_items)
        new_index = win32gui.SendMessage(hwndList, commctrl.LVM_INSERTITEM, 0, item.toparam())
        item = LVITEM(text=obj[1], iItem = new_index, iSubItem = 1)
        win32gui.SendMessage(hwndList, commctrl.LVM_SETITEM, 0, item.toparam())

def SetDefaultContact(txtProcessor,*args):
    # Acquiring the control of the text box
    txt_name = txtProcessor.GetControl()
    txt_email = txtProcessor.GetControl(txtProcessor.other_ids[0])

    global name
    global email
    if txtProcessor.init_done:
        win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.control_id,name)
        win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[0],email)
        return
    #
    try:
        mail = GetMail(txtProcessor)
        name = ustr(mail.SenderName).encode('iso-8859-1')
        email = ustr(mail.SenderEmailAddress).encode('iso-8859-1')
    except Exception,e:
        pass

    fs_combo = win32gui.GetDlgItem(txtProcessor.window.hwnd, txtProcessor.other_ids[1])
    c_combo = win32gui.GetDlgItem(txtProcessor.window.hwnd, txtProcessor.other_ids[2])
    win32gui.SendMessage(fs_combo, win32con.CB_SETCURSEL, -1 )
    win32gui.SendMessage(c_combo, win32con.CB_SETCURSEL, -1 )
    win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.control_id,name)
    win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[0],email)
    txtProcessor.init_done = True

def setCheckList(groupProcessor,*args):
    try:
        child_style = win32con.BS_AUTOCHECKBOX | win32con.WS_TABSTOP
        hinst = win32gui.dllhandle
        objs = groupProcessor.window.manager.config['objects']
        ins_objs = NewConn.GetAllObjects()
        left = 20
        top = 60
        cnt=0
        id=4001
        id1=6001
        load_bmp_flags=win32con.LR_LOADFROMFILE | win32con.LR_LOADTRANSPARENT
        if groupProcessor.init_done:
           return
        else:
           for obj in objs:
             if obj[1] in ins_objs:
                groupProcessor.init_done = True
                #Add image
                hwndImg = win32gui.CreateWindowEx(0, "STATIC","",
                                            win32con.SS_CENTERIMAGE | win32con.SS_REALSIZEIMAGE | win32con.SS_BITMAP | win32con.WS_CHILD | win32con.WS_VISIBLE,
                                            left,top+3,13,13,
                                            groupProcessor.window.hwnd,
                                            id,
                                            0,
                                            None
                                            );
                image_path = os.path.join(groupProcessor.window.manager.application_directory, "dialogs\\resources\\openerp_logo1.bmp")
                if obj[2]:
                    image_path = obj[2]
                try:
                    hicon = win32gui.LoadImage(0, image_path, win32con.IMAGE_BITMAP, 40, 40, load_bmp_flags)
                except Exception,e:
                    msg="Problem loading the image \n\n" + getMessage(e)
                    hicon = None
                    win32ui.MessageBox(msg, "Load Image", flag_error)

                win32gui.SendMessage(hwndImg, win32con.STM_SETIMAGE, win32con.IMAGE_BITMAP, hicon);
                #Add Checkbox
                left+= 17
                hwndChk = win32gui.CreateWindowEx(
                                                    0,"BUTTON",obj[0],win32con.WS_VISIBLE | win32con.WS_CHILD | \
                                                    win32con.BS_AUTOCHECKBOX | win32con.WS_TABSTOP | win32con.BST_CHECKED, \
                                                    left, top, 130,20,groupProcessor.window.hwnd,id1,hinst,None
                                                  )
                if obj[1] in ['res.partner','res.partner.address']:
                    win32gui.SendMessage(hwndChk , win32con.BM_SETCHECK, 1, 0);
                hwndChk_list.append((id1,hwndChk))

                cnt=cnt+1
                id+=1
                id1+=1
                left+=17
                win32gui.UpdateWindow(hwndImg)
                left+=140
                if cnt > 1:
                    left = 20
                    top+=18
                    cnt=0
    except Exception, e:
        win32ui.MessageBox(str(e), 'Document List')

def CreatePartner(btnProcessor,*args):
    #Check if server running or user logged in
    b = check()
    if not b:
        return

    partner_name = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
    if not partner_name:
        win32ui.MessageBox("Please enter Partner name.", "Create Partner", flag_excl)
        return
    res = {'name':ustr(partner_name)}
    try:
        id = NewConn.CreatePartner(str(res))
    except Exception,e:
        msg="Partner not created \n\n" + getMessage(e)
        win32ui.MessageBox(msg, "Create Partner", flag_error)
        return
    if id:
        win32ui.MessageBox("New Partner '%s' created."%partner_name, "Create Partner", flag_info)
        win32gui.EndDialog(btnProcessor.window.hwnd, btnProcessor.id)
    else:
        win32ui.MessageBox("Partner '%s' already Exists."%partner_name, "Create Partner", flag_info)
    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0],'')

def set_search_text(dialogProcessor,*args):
    global search_text
    search_text = win32gui.GetDlgItemText(dialogProcessor.window.hwnd, dialogProcessor.other_ids[0])
    return

def set_name_email(dialogProcessor,*args):
    global name
    global email
    name = win32gui.GetDlgItemText(dialogProcessor.window.hwnd, dialogProcessor.other_ids[0])
    email = win32gui.GetDlgItemText(dialogProcessor.window.hwnd, dialogProcessor.other_ids[1])

def GetDefaultEmail(txtProcessor,*args):

    from win32com.client import Dispatch
    import win32con
    b = check()
    if not b:
        return
    #Acquiring control of the text box
    search_partner_box = txtProcessor.GetControl()
    global search_partner_text
    if txtProcessor.init_done:
        win32gui.SendMessage(search_partner_box, win32con.WM_SETTEXT, 0,search_partner_text)
        return
    #Reading Current Selected Email.
    ex = txtProcessor.window.manager.outlook.ActiveExplorer()
    assert ex.Selection.Count == 1
    mail = ex.Selection.Item(1)
    #Fetching Sender MailID from Selected Mail
    try:
        search_partner_text = ustr(mail.SenderEmailAddress).encode('iso-8859-1')
    except Exception,e:
        win32ui.MessageBox("Error In reading email ID from Email ","Open Contact", flag_error)
        pass
    win32gui.SendMessage(search_partner_box, win32con.WM_SETTEXT, 0, search_partner_text)

    fs_combo = win32gui.GetDlgItem(txtProcessor.window.hwnd, txtProcessor.other_ids[10])
    c_combo = win32gui.GetDlgItem(txtProcessor.window.hwnd, txtProcessor.other_ids[11])
    partner_combo = win32gui.GetDlgItem(txtProcessor.window.hwnd, txtProcessor.other_ids[0])
    vals = []
    #Searching the res.partner.address for contact based on Sender Mail ID.
    vals = NewConn.SearchPartnerDetail(search_partner_text)
    #If no user Found.
    if vals == None:
        for i in range(1,10):
            win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[i], "")
        win32gui.SendMessage(fs_combo, win32con.CB_SETCURSEL, -1 )
        win32gui.SendMessage(c_combo, win32con.CB_SETCURSEL, -1 )
        win32gui.SendMessage(partner_combo, win32con.CB_SETCURSEL, -1 )
        win32ui.MessageBox("No matching records found for  : "+str(search_partner)+".","Open Contact", flag_excl)
        return
    else:
        #If user Found than Setting the Value for the contact in fields.
        for i in range(1,10):
            win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[i], "")
        win32gui.SendMessage(fs_combo, win32con.CB_SETCURSEL, -1 )
        win32gui.SendMessage(c_combo, win32con.CB_SETCURSEL, -1 )
        win32gui.SendMessage(partner_combo, win32con.CB_SETCURSEL, -1 )

        for val in vals:

            if val[0] == 'partner_id':
                    temp = list (NewConn.GetPartners())
                    i = -1
                    for t in temp:
                        i+=1
                        if t[1] == val[1][1] :
                            win32gui.SendMessage(partner_combo, win32con.CB_SETCURSEL, i )
            if val[0] == 'name' and val[1] != False :
                win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[1], str(val[1]))

            if val[0] == 'street' and val[1] != False :
                win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[2], str(val[1]))

            if val[0] == 'street2' and val[1] != False :
                win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[3], str(val[1]))

            if val[0] == 'zip' and val[1] != False :
                win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[9], str(val[1]))

            if val[0] == 'city' and val[1] != False :
                win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[4], str(val[1]))

            if val[0] == 'state_id' and val[1] != False :
                id = i = -1
                temp = list(NewConn.GetAllState())
                for t in temp:
                    i+=1
                    if str(t[1]) ==  str(val[1][1]):
                        id = i
                        break;
                sel = win32gui.SendMessage(fs_combo, win32con.CB_SETCURSEL, id )

            if val[0] == 'country_id' and val[1] != False :
                id = i = -1
                temp = list(NewConn.GetAllCountry())
                for t in temp:
                    i+=1
                    if str(t[1]) ==  str(val[1][1]):
                        id = i
                        break;
                sel = win32gui.SendMessage(c_combo, win32con.CB_SETCURSEL, id )

            if val[0] == 'phone' and val[1] != False :
                win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[5], str(val[1]))

            if val[0] == 'mobile' and val[1] != False :
                win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[6], str(val[1]))

            if val[0] == 'fax' and val[1] != False :
                win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[7], str(val[1]))

            if val[0] == 'email' and val[1] != False :
                win32gui.SetDlgItemText(txtProcessor.window.hwnd, txtProcessor.other_ids[8], str(val[1]))

    txtProcessor.init_done=True

def SearchPartner(btnProcessor,*args):
    b = check()
    if not b:
        return
    #hwnd For the List box
    fs_combo = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[11])
    c_combo = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[12])
    partner_combo = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[1])
    try :
        search_partner = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
        if not search_partner:
            win32ui.MessageBox("Please enter email id to search for.", "Open Contact", flag_excl)
            return
        vals = []
        #Searching the contact.
        vals = NewConn.SearchPartnerDetail(search_partner)
        #if contact not found resetting all field to blank
        if vals == None:
            for i in range(2,11):
                win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[i], "")
            win32gui.SendMessage(fs_combo, win32con.CB_SETCURSEL, -1 )
            win32gui.SendMessage(c_combo, win32con.CB_SETCURSEL, -1 )
            win32gui.SendMessage(partner_combo, win32con.CB_SETCURSEL, -1 )
            win32ui.MessageBox("No matching records found for  : "+str(search_partner)+".","Open Contact", flag_excl)
            win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0], "<enter new search>")
            return
        #if contact found than setting the values for the contact.
        else:
            for i in range(2,11):
                win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[i], "")
            win32gui.SendMessage(fs_combo, win32con.CB_SETCURSEL, -1 )
            win32gui.SendMessage(c_combo, win32con.CB_SETCURSEL, -1 )
            win32gui.SendMessage(partner_combo, win32con.CB_SETCURSEL, -1 )
            for val in vals:
                if val[0] == 'partner_id':
                    #Finding the partner index in list and setting it.
                    temp = list (NewConn.GetPartners())
                    i = -1
                    for t in temp:
                        i+=1
                        if t[1] == val[1][1] :
                            win32gui.SendMessage(partner_combo, win32con.CB_SETCURSEL, i )

                if val[0] == 'name' and val[1] != False :
                    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[2], str(val[1]))

                if val[0] == 'street' and val[1] != False :
                    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[3], str(val[1]))

                if val[0] == 'street2' and val[1] != False :
                    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[4], str(val[1]))

                if val[0] == 'zip' and val[1] != False :
                    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[10], str(val[1]))

                if val[0] == 'city' and val[1] != False :
                    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[5], str(val[1]))

                if val[0] == 'state_id' and val[1] != False :
                    #Finding the state index in list and setting it.
                    id = i = -1
                    temp = list(NewConn.GetAllState())
                    for t in temp:
                        i+=1
                        if str(t[1]) ==  str(val[1][1]):
                            id = i
                            break;
                    sel = win32gui.SendMessage(fs_combo, win32con.CB_SETCURSEL, id )

                if val[0] == 'country_id' and val[1] != False :
                    #Finding the country index in list and setting it.
                    id = i = -1
                    temp = list(NewConn.GetAllCountry())
                    for t in temp:
                        i+=1
                        if str(t[1]) ==  str(val[1][1]):
                            id = i
                            break;
                    sel = win32gui.SendMessage(c_combo, win32con.CB_SETCURSEL, id )

                if val[0] == 'phone' and val[1] != False :
                    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[6], str(val[1]))

                if val[0] == 'mobile' and val[1] != False :
                    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[7], str(val[1]))

                if val[0] == 'fax' and val[1] != False :
                    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[8], str(val[1]))

                if val[0] == 'email' and val[1] != False :
                    win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[9], str(val[1]))

            win32gui.SetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[0], "<Enter  new search>")
    except Exception,e:
        msg = getMessage(e)
        win32ui.MessageBox(msg, "Open Contact", flag_error)
        pass

def WritePartner(btnProcessor,*args):
    new_vals=[]
    #Reading new value of the fields.
    contect_name = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[1])
    street = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[2])
    street2 = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[3])
    city = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[4])
    phone = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[7])
    mobile = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[8])
    fax = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[9])
    email = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[10])
    zip = win32gui.GetDlgItemText(btnProcessor.window.hwnd, btnProcessor.other_ids[11])
    country_combo = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[6])
    country_sel = win32gui.SendMessage(country_combo, win32con.CB_GETCURSEL)
    state_combo = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[5])
    state_sel = win32gui.SendMessage(state_combo, win32con.CB_GETCURSEL)
    partner_combo = win32gui.GetDlgItem(btnProcessor.window.hwnd, btnProcessor.other_ids[0])
    partner_sel = win32gui.SendMessage(partner_combo, win32con.CB_GETCURSEL)
    #Checking that record not being saved without name or Partner
    if contect_name.strip() == "":
        win32ui.MessageBox("Please enter partner Contact Name name.", "Open Contact", flag_excl)
        return
    if partner_sel < 1:
        win32ui.MessageBox("Please Select Partner From list.", "Open Contact", flag_excl)
        return
    fs_id = c_id = p_id = -1
    #Finding the partner index in list finding it record ID.
    if not partner_sel < 0 :
        try:
            temp = NewConn.GetPartners()
            i = -1
            for t in temp:
                i+=1
                if i == partner_sel:
                    p_id = t[0]
                    break;
        except Exception, e:
            msg = getMessage(e)
            win32ui.MessageBox(msg, "Open Contact", flag_error)
            pass
    #Finding the State index in list finding it record ID.
    if not state_sel == -1 :
        try:
            temp = NewConn.GetAllState()
            i = -1
            for t in temp:
                i+=1
                if i == state_sel:
                    fs_id = t[0]
                    break;
        except Exception, e:
            msg = getMessage(e)
            win32ui.MessageBox(msg, "Open Contact", flag_error)
            pass
    #Finding the country index in list finding it record ID.
    if not country_sel == -1 :
        try:
            temp = NewConn.GetAllCountry()
            i = -1
            for t in temp:
                i+=1
                if i == country_sel:
                    c_id = t[0]
                    break;
        except Exception, e:
            msg = getMessage(e)
            win32ui.MessageBox(msg, "Open Contact", flag_error)
            pass
    # Creating a list to write the values to the OpenERP
    new_vals.append(['partner_id',p_id])
    new_vals.append(['name',contect_name])
    new_vals.append(['street',street])
    new_vals.append(['street2',street2])
    new_vals.append(['city',city])
    new_vals.append(['state_id',fs_id])
    new_vals.append(['country_id',c_id])
    new_vals.append(['phone',phone])
    new_vals.append(['mobile',mobile])
    new_vals.append(['email',email])
    new_vals.append(['fax',fax])
    new_vals.append(['zip',zip])
    flag = 0
    try:
        #writing the updated values to the Server.
        flag = NewConn.WritePartnerValues(new_vals)
    except Exception,e:
        msg = getMessage(e)
        win32ui.MessageBox(msg, "Open Contact", flag_error)
        pass
    if flag == 1:
        win32ui.MessageBox("Changes have been Updated Successfully.", "Open Contact", flag_info)
    elif flag == 0:
        win32ui.MessageBox("Error in Updating the Changes.\n Please check the Database Connection.", "Open Contact", flag_error)
    elif flag == -1:
        win32ui.MessageBox("Contact can not be Save.\nFirst select contact using Search.","Open Contact", flag_info)



dialog_map = {
            "IDD_MANAGER" :            (
                (CancelButtonProcessor,    "IDCANCEL", resetConnAttribs, ()),
                (TabProcessor,             "IDC_TAB IDC_LIST",
                                           """IDD_GENERAL IDD_OBJECT_SETTINGS IDD_ABOUT"""),
                (DoneButtonProcessor,      "ID_DONE"),
            ),

            "IDD_GENERAL":             (
                (DBComboProcessor,          "ID_DB_DROPDOWNLIST", GetConn, ()),
                (TextProcessor,             "ID_SERVER_PORT ID_USERNAME ID_PASSWORD", SetAllText, ()),
                (CommandButtonProcessor,    "ID_BUT_TESTCONNECTION ID_DB_DROPDOWNLIST ID_USERNAME \
                                            ID_PASSWORD", TestConnection, ()),
                (CommandButtonProcessor,    "IDC_RELOAD", ReloadAllControls, ()),
                (DialogCommand,             "IDC_BUT_SET_SERVER_PORT", "IDD_SERVER_PORT_DIALOG"),
            ),

            "IDD_OBJECT_SETTINGS" :    (
                (CommandButtonProcessor,   "IDC_BUT_LOAD_IMAGE IDC_IMAGE_PATH", GetImagePath, ()),
                (CommandButtonProcessor,   "IDC_BUT_SAVE_OBJECT IDC_OBJECT_TITLE IDC_OBJECT_NAME \
                                            IDC_IMAGE_PATH IDC_LIST", AddNewObject, ()),
                (CommandButtonProcessor,   "IDC_BUT_DEL_OBJECT IDC_LIST", DeleteSelectedObjects, ()),
                (ListBoxProcessor,         "IDC_LIST", SetDefaultList, ())
            ),

            "IDD_ABOUT" :              (
                (ImageProcessor,          "IDB_OPENERPLOGO"),
                (MessageProcessor,        "IDC_ABOUT"),
            ),

            "IDD_SERVER_PORT_DIALOG" : (
                (CloseButtonProcessor,    "IDCANCEL"),
                (OKButtonProcessor,  "IDOK ID_SERVER ID_PORT IDR_XML_PROTOCOL"),
                (RadioButtonProcessor, "IDR_XML_PROTOCOL", GetConn, ()),
                (RadioButtonProcessor, "IDR_XMLS_PROTOCOL", GetConn, ()),
                (RadioButtonProcessor, "IDR_NETRPC_PROTOCOL", GetConn, ()),
            ),

            "IDD_SYNC" :               (
                (CommandButtonProcessor,    "ID_SEARCH ID_SEARCH_TEXT IDC_NAME_LIST", SearchObjectsForText,()),
                (GroupProcessor,            "IDC_STATIC_GROUP", setCheckList, ()),
                (CSComboProcessor,          "ID_ATT_METHOD_DROPDOWNLIST", GetConn,()),
                (TextProcessor,             "ID_SEARCH_TEXT", GetSearchText, ()),
                (DialogCommand,             "ID_CREATE_CONTACT ID_SEARCH_TEXT", "IDD_NEW_CONTACT_DIALOG", set_search_text, ()),
                (CloseButtonProcessor,      "IDCANCEL"),
                (CommandButtonProcessor,    "ID_MAKE_ATTACHMENT IDC_NAME_LIST IDD_SYNC", MakeAttachment, ()),
                (CommandButtonProcessor,    "ID_CREATE_CASE ID_ATT_METHOD_DROPDOWNLIST IDC_NAME_LIST", CreateCase, ()),
                (ListBoxProcessor,          "IDC_NAME_LIST", SetNameColumn, ())
            ),

            "IDD_NEW_CONTACT_DIALOG" : (
                (PartnersComboProcessor,    "ID_PARTNER_DROPDOWNLIST", GetConn, ()),
                (CountryComboProcessor,     "ID_COUNTRY_DROPLIST", GetConn, ()),
                (StateComboProcessor,       "ID_FED_STATE_DROPLIST", GetConn, ()),
                (CloseButtonProcessor,      "IDCANCEL"),
                (CommandButtonProcessor,    "ID_CONTACT_SAVE_BUTTON ID_CONTACT_NAME_TEXT ID_CONTACT_EMAIL_TEXT ID_CONTACT_OFFICE_TEXT ID_CONTACT_MOBILE_TEXT ID_FAX_TEXT ID_STREET_TEXT ID_STREET2_TEXT ID_PARTNER_CITY_TEXT ID_ZIP_TEXT ID_PARTNER_DROPDOWNLIST ID_FED_STATE_DROPLIST ID_COUNTRY_DROPLIST", CreateContact, ()),
                (TextProcessor,             "ID_CONTACT_NAME_TEXT ID_CONTACT_EMAIL_TEXT ID_FED_STATE_DROPLIST ID_COUNTRY_DROPLIST" , SetDefaultContact, ()),
                (DialogCommand,             "ID_NEW_PARTNER_BUTTON ID_CONTACT_NAME_TEXT ID_CONTACT_EMAIL_TEXT", "IDD_NEW_PARTNER_DIALOG", set_name_email, ()),
            ),

            "IDD_NEW_PARTNER_DIALOG" : (
                (CloseButtonProcessor,      "IDCANCEL"),
                (CommandButtonProcessor,    "ID_SAVE_PARTNER_BUTTON ID_PARTNER_NAME_TEXT", CreatePartner, ()),
            ),

            "IDD_VIEW_PARTNER_DIALOG" : (
                (PartnersComboProcessor,    "ID_PARTNER_DROPLIST", GetConn, ()),
                (StateComboProcessor,       "ID_ALL_STATE_DROPDOWNLIST", GetConn, ()),
                (CountryComboProcessor,     "ID_ALL_COUNTRY_DROPDOWNLIST", GetConn, ()),
                (TextProcessor,             "IDET_SEARCH_PARTNER ID_PARTNER_DROPLIST IDET_PARTNER_CONTACT_NAME IDET_PARTNER_STREET IDET_PARTNER_STREET2 IDET_PARTNER_CITY IDET_PARTNER_OFFICENO IDET_PARTNER_MOBILENO IDET_PARTNER_EMAIL IDET_PARTNER_FAX IDET_ZIP ID_ALL_STATE_DROPDOWNLIST ID_ALL_COUNTRY_DROPDOWNLIST", GetDefaultEmail, ()),
                (CommandButtonProcessor,    "IDPB_SEARCH_PARTNER IDET_SEARCH_PARTNER ID_PARTNER_DROPLIST IDET_PARTNER_CONTACT_NAME IDET_PARTNER_STREET IDET_PARTNER_STREET2 IDET_PARTNER_CITY IDET_PARTNER_OFFICENO IDET_PARTNER_MOBILENO IDET_PARTNER_EMAIL IDET_PARTNER_FAX IDET_ZIP ID_ALL_STATE_DROPDOWNLIST ID_ALL_COUNTRY_DROPDOWNLIST", SearchPartner, ()),
                (CommandButtonProcessor,    "IDPB_WRITE_CHANGES ID_PARTNER_DROPLIST IDET_PARTNER_CONTACT_NAME IDET_PARTNER_STREET IDET_PARTNER_STREET2 IDET_PARTNER_CITY ID_ALL_STATE_DROPDOWNLIST ID_ALL_COUNTRY_DROPDOWNLIST IDET_PARTNER_OFFICENO IDET_PARTNER_MOBILENO IDET_PARTNER_EMAIL IDET_PARTNER_FAX IDET_ZIP", WritePartner, ()),
                (CloseButtonProcessor,      "IDCANCEL"),
                (DialogCommand,             "ID_NEW_PART_BUTTON", "IDD_NEW_PARTNER_DIALOG" ),
                (DialogCommand,             "IDPB_NEWPARTNER_BUTTON" , "IDD_NEW_CONTACT_DIALOG")
            ),
}
