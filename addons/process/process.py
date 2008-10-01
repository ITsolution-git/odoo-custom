# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2005-TODAY TINY SPRL. (http://tiny.be) All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import netsvc
import pooler, tools

from osv import fields, osv

class Env(dict):
    
    def __init__(self, obj, user):
        self.__obj = obj
        self.__usr = user
        
    def __getitem__(self, name):
        
        if name in ('__obj', '__user'):
            return super(ExprContext, self).__getitem__(name)
        
        if name == 'user':
            return self.__user
        
        if name == 'object':
            return self.__obj
        
        return self.__obj[name]

class process_process(osv.osv):
    _name = "process.process"
    _description = "Process"
    _columns = {
        'name': fields.char('Name', size=30,required=True, translate=True),
        'active': fields.boolean('Active'),
        'note': fields.text('Notes', translate=True),
        'node_ids': fields.one2many('process.node', 'process_id', 'Nodes')
    }
    _defaults = {
        'active' : lambda *a: True,
    }

    def search_by_model(self, cr, uid, res_model, context):
        pool = pooler.get_pool(cr.dbname)

        model_ids = pool.get('ir.model').search(cr, uid, [('model', '=', res_model)])
        if not model_ids:
            return []

        nodes = pool.get('process.node').search(cr, uid, [('model_id', 'in', model_ids)])
        if not nodes:
            return []

        nodes = pool.get('process.node').browse(cr, uid, nodes, context)

        unique = []
        result = []
        
        for node in nodes:
            if node.process_id.id not in unique:
                result.append((node.process_id.id, node.process_id.name))
                unique.append(node.process_id.id)

        return result

    def graph_get(self, cr, uid, id, res_model, res_id, scale, context):
        
        pool = pooler.get_pool(cr.dbname)
        
        process = pool.get('process.process').browse(cr, uid, [id])[0]
        current_object = pool.get(res_model).browse(cr, uid, [res_id], context)[0]
        current_user = pool.get('res.users').browse(cr, uid, [uid], context)[0]
        
        expr_context = Env(current_object, current_user)
        
        notes = process.note
        nodes = {}
        start = []
        transitions = {}

        states = dict(pool.get(res_model).fields_get(cr, uid, context=context).get('state', {}).get('selection', {}))
        title = "%s - Resource: %s, State: %s" % (process.name, current_object.name, states.get(getattr(current_object, 'state'), 'N/A'))

        perm = pool.get(res_model).perm_read(cr, uid, [res_id], context)[0]

        for node in process.node_ids:
            data = {}
            data['name'] = node.name
            data['model'] = (node.model_id or None) and node.model_id.model
            data['kind'] = node.kind
            data['subflow'] = (node.subflow_id or False) and [node.subflow_id.id, node.subflow_id.name]
            data['notes'] = node.note
            data['active'] = False
            data['gray'] = False
            data['url'] = node.help_url

            # get assosiated workflow
            if data['model']:
                wkf_ids = self.pool.get('workflow').search(cr, uid, [('osv', '=', data['model'])])
                data['workflow'] = (wkf_ids or False) and wkf_ids[0]

            if node.menu_id:
                data['menu'] = {'name': node.menu_id.complete_name, 'id': node.menu_id.id}
            
            if node.model_id and node.model_id.model == res_model:
                try:
                    data['active'] = eval(node.model_states, expr_context)
                except Exception, e:
                    # waring: invalid state expression
                    pass

            if not data['active']:
                try:
                    gray = True
                    for cond in node.condition_ids:
                        if cond.model_id and cond.model_id.model == res_model:
                            gray = gray and eval(cond.model_states, expr_context)
                    data['gray'] = not gray
                except:
                    pass

            nodes[node.id] = data
            if node.flow_start:
                start.append(node.id)

            for tr in node.transition_out:
                data = {}
                data['name'] = tr.name
                data['source'] = tr.source_node_id.id
                data['target'] = tr.target_node_id.id
                data['notes'] = tr.note
                data['buttons'] = buttons = []
                for b in tr.action_ids:
                    button = {}
                    button['name'] = b.name
                    button['state'] = b.state
                    button['action'] = b.action
                    buttons.append(button)
                data['roles'] = roles = []
                for r in tr.transition_ids:
                    if r.role_id:
                        role = {}
                        role['name'] = r.role_id.name
                        roles.append(role)
                for r in tr.role_ids:
                    role = {}
                    role['name'] = r.name
                    roles.append(role)
                transitions[tr.id] = data

        # now populate resource information
        def update_relatives(nid, ref_id, ref_model):
            relatives = []

            for tid, tr in transitions.items():
                if tr['source'] == nid:
                    relatives.append(tr['target'])
                if tr['target'] == nid:
                    relatives.append(tr['source'])

            if not ref_id:
                nodes[nid]['res'] = False
                return

            nodes[nid]['res'] = resource = {'id': ref_id, 'model': ref_model}

            refobj = pool.get(ref_model).browse(cr, uid, [ref_id], context)[0]
            fields = pool.get(ref_model).fields_get(cr, uid, context=context)

            # chech whether directory_id from inherited from document module
            if 'directory_id' in refobj and refobj.directory_id:
                res['directory'] = self.pool.get('document.directory').get_resource_path(cr, uid, node.directory_id.id, ref_model, ref_id)

            resource['name'] = refobj.name_get(context)[0][1]
            resource['perm'] = pool.get(ref_model).perm_read(cr, uid, [ref_id], context)[0]

            for r in relatives:
                node = nodes[r]
                if 'res' not in node:
                    for n, f in fields.items():
                        if node['model'] == ref_model:
                            update_relatives(r, ref_id, ref_model)

                        elif f.get('relation') == node['model']:
                            rel = refobj[n]
                            if rel and isinstance(rel, list) :
                                rel = rel[0]
                            try: # XXX: rel has been reported as string (check it)
                                _id = (rel or False) and rel.id
                                _model = node['model']
                                update_relatives(r, _id, _model)
                            except:
                                pass

        for nid, node in nodes.items():
            if not node['gray'] and (node['active'] or node['model'] == res_model):
                update_relatives(nid, res_id, res_model)
                break

        # calculate graph layout
        g = tools.graph(nodes.keys(), map(lambda x: (x['source'], x['target']), transitions.values()))
        g.process(start)        
        g.scale(*scale) #g.scale(100, 100, 180, 120)
        graph = g.result_get()

        # fix the height problem
        miny = -1
        for k,v in nodes.items():
            x = graph[k]['y']
            y = graph[k]['x']
            if miny == -1:
                miny = y
            miny = min(y, miny)
            v['x'] = x
            v['y'] = y

        for k, v in nodes.items():
            y = v['y']
            v['y'] = min(y - miny + 10, y)

        return dict(title=title, perm=perm, notes=notes, nodes=nodes, transitions=transitions)

    def copy(self, cr, uid, id, default=None, context={}):
        """ Deep copy the entire process.
        """

        if not default:
            default = {}

        pool = pooler.get_pool(cr.dbname)
        process = pool.get('process.process').browse(cr, uid, [id], context)[0]

        nodes = {}
        transitions = {}

        # first copy all nodes and and map the new nodes with original for later use in transitions
        for node in process.node_ids:
            for t in node.transition_in:
                tr = transitions.setdefault(t.id, {})
                tr['target'] = node.id
            for t in node.transition_out:
                tr = transitions.setdefault(t.id, {})
                tr['source'] = node.id
            nodes[node.id] = pool.get('process.node').copy(cr, uid, node.id, context=context)

        # then copy transitions with new nodes
        for tid, tr in transitions.items():
            vals = {
                'source_node_id': nodes[tr['source']],
                'target_node_id': nodes[tr['target']]
            }
            tr = pool.get('process.transition').copy(cr, uid, tid, default=vals, context=context)

        # and finally copy the process itself with new nodes
        default.update({
            'active': True,
            'node_ids': [(6, 0, nodes.values())]
        })
        return super(process_process, self).copy(cr, uid, id, default, context)

process_process()

class process_node(osv.osv):
    _name = 'process.node'
    _description ='Process Nodes'
    _columns = {
        'name': fields.char('Name', size=30,required=True, translate=True),
        'process_id': fields.many2one('process.process', 'Process', required=True, ondelete='cascade'),
        'kind': fields.selection([('state','State'), ('subflow','Subflow')], 'Kind of Node', required=True),
        'menu_id': fields.many2one('ir.ui.menu', 'Related Menu'),
        'note': fields.text('Notes', translate=True),
        'model_id': fields.many2one('ir.model', 'Object', ondelete='set null'),
        'model_states': fields.char('States Expression', size=128),
        'subflow_id': fields.many2one('process.process', 'Subflow', ondelete='set null'),
        'flow_start': fields.boolean('Starting Flow'),
        'transition_in': fields.one2many('process.transition', 'target_node_id', 'Starting Transitions'),
        'transition_out': fields.one2many('process.transition', 'source_node_id', 'Ending Transitions'),
        'condition_ids': fields.one2many('process.condition', 'node_id', 'Conditions'),
        'help_url': fields.char('Help URL', size=255)
    }
    _defaults = {
        'kind': lambda *args: 'state',
        'model_states': lambda *args: False,
        'flow_start': lambda *args: False,
    }

    def copy(self, cr, uid, id, default=None, context={}):
        if not default:
            default = {}
        default.update({
            'transition_in': [],
            'transition_out': []
        })
        return super(process_node, self).copy(cr, uid, id, default, context)

process_node()

class process_node_condition(osv.osv):
    _name = 'process.condition'
    _description = 'Condition'
    _columns = {
        'name': fields.char('Name', size=30, required=True),
        'node_id': fields.many2one('process.node', 'Node', required=True, ondelete='cascade'),
        'model_id': fields.many2one('ir.model', 'Object', ondelete='set null'),
        'model_states': fields.char('Expression', required=True, size=128)
    }
process_node_condition()

class process_transition(osv.osv):
    _name = 'process.transition'
    _description ='Process Transitions'
    _columns = {
        'name': fields.char('Name', size=32, required=True, translate=True),
        'source_node_id': fields.many2one('process.node', 'Source Node', required=True, ondelete='cascade'),
        'target_node_id': fields.many2one('process.node', 'Target Node', required=True, ondelete='cascade'),
        'action_ids': fields.one2many('process.transition.action', 'transition_id', 'Buttons'),
        'transition_ids': fields.many2many('workflow.transition', 'process_transition_ids', 'ptr_id', 'wtr_id', 'Workflow Transitions'),
        'role_ids': fields.many2many('res.roles', 'process_transition_roles_rel', 'tid', 'rid', 'Roles'),
        'note': fields.text('Description', translate=True),
    }
process_transition()

class process_transition_action(osv.osv):
    _name = 'process.transition.action'
    _description ='Process Transitions Actions'
    _columns = {
        'name': fields.char('Name', size=32, required=True, translate=True),
        'state': fields.selection([('dummy','Dummy'),
                                   ('object','Object Method'),
                                   ('workflow','Workflow Trigger'),
                                   ('action','Action')], 'Type', required=True),
        'action': fields.char('Action ID', size=64, states={
            'dummy':[('readonly',1)],
            'object':[('required',1)],
            'workflow':[('required',1)],
            'action':[('required',1)],
        },),
        'transition_id': fields.many2one('process.transition', 'Transition', required=True, ondelete='cascade')
    }
    _defaults = {
        'state': lambda *args: 'dummy',
    }

    def copy(self, cr, uid, id, default=None, context={}):
        if not default:
            default = {}

        state = self.pool.get('process.transition.action').browse(cr, uid, [id], context)[0].state
        if state:
            default['state'] = state

        return super(process_transition_action, self).copy(cr, uid, id, default, context)

process_transition_action()

