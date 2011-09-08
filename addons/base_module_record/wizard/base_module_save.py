# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import zipfile
import StringIO
import base64

import tools
from tools.translate import _
from osv import osv, fields


def _create_yaml(self, cr, uid, data, context=None):
    mod = self.pool.get('ir.module.record')
    try:
        res_xml = mod.generate_yaml(cr, uid)
    except Exception, e:
        raise osv.except_osv(_('Error'),_(str(e)))
    return {
    'yaml_file': base64.encodestring(res_xml),
}
    
def _create_module(self, cr, uid, ids, context=None):
    mod = self.pool.get('ir.module.record')
    res_xml = mod.generate_xml(cr, uid)
    data = self.read(cr, uid, ids, [], context=context)[0]
    s = StringIO.StringIO()
    zip = zipfile.ZipFile(s, 'w')
    dname = data['directory_name']
    data['update_name'] = ''
    data['demo_name'] = ''
    if ['data_kind'] =='demo':
        data['demo_name'] = '"%(directory_name)s_data.xml"' % data
    else:
        data['update_name'] = '"%(directory_name)s_data.xml"' % data
    data['depends'] = ','.join(map(lambda x: '"'+x+'"', mod.depends.keys()))
    _terp = """{
        "name" : "%(name)s",
        "version" : "%(version)s",
        "author" : "%(author)s",
        "website" : "%(website)s",
        "category" : "%(category)s",
        "description": \"\"\"%(description)s\"\"\",
        "depends" : [%(depends)s],
        "init_xml" : [ ],
        "demo_xml" : [ %(demo_name)s],
        "update_xml" : [%(update_name)s],
        "installable": True
} """ % data
    filewrite = {
        '__init__.py':'#\n# Generated by the OpenERP module recorder !\n#\n',
        '__openerp__.py':_terp,
        dname+'_data.xml': res_xml
    }
    for name,datastr in filewrite.items():
        info = zipfile.ZipInfo(dname+'/'+name)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 2175008768
        if not datastr:
            datastr = ''
        zip.writestr(info, datastr)
    zip.close()
    return {
        'module_file': base64.encodestring(s.getvalue()),
        'module_filename': data['directory_name']+'-'+data['version']+'.zip'
    }

class base_module_save(osv.osv_memory):
    _name = 'base.module.save'
    _description = "Base Module Save"

    def default_get(self, cr, uid, fields, context=None):
        mod = self.pool.get('ir.module.record')
        result = {}
        info = "Details of "+str(len(mod.recording_data))+" Operation(s):\n\n"
        res = super(base_module_save, self).default_get(cr, uid, fields, context=context)
        for line in mod.recording_data:
            result.setdefault(line[0],{})
            result[line[0]].setdefault(line[1][3], {})
            result[line[0]][line[1][3]].setdefault(line[1][3], 0)
            result[line[0]][line[1][3]][line[1][3]]+=1
        for key1,val1 in result.items():
            info+=key1+"\n"
            for key2,val2 in val1.items():
                info+="\t"+key2+"\n"
                for key3,val3 in val2.items():
                    info+="\t\t"+key3+" : "+str(val3)+"\n"
        if 'info_text' in fields:
            res.update({'info_text': info})
        if 'info_status' in fields:
            info_status = mod.recording and 'record' or 'no'
            res.update({'info_status': info_status})
        return res
    
    _columns = {
        'info_text': fields.text('Information', readonly=True),
        'info_status': fields.selection([('no', 'Not Recording'),('record', 'Recording')], 'Status', readonly=True),
        'info_yaml': fields.boolean('YAML'),
    }

    def record_save(self, cr, uid, ids, context=None):
        data = self.read(cr, uid, ids, [], context=context)[0]
        mod = self.pool.get('ir.module.record')
        mod_obj = self.pool.get('ir.model.data')
        if len(mod.recording_data):
            if data['info_yaml']:
                mod = self.pool.get('ir.module.record')
                res=_create_yaml(self, cr, uid, data, context)
                model_data_ids = mod_obj.search(cr, uid,[('model', '=', 'ir.ui.view'), ('name', '=', 'yml_save_form_view')], context=context)
                resource_id = mod_obj.read(cr, uid, model_data_ids, fields=['res_id'], context=context)[0]['res_id']
                return {
                    'name': _('Message'),
                    'context':  {
                        'default_yaml_file': tools.ustr(res['yaml_file']),
                        },
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'base.module.record.objects',
                    'views': [(resource_id, 'form')],
                    'type': 'ir.actions.act_window',
                    'target': 'new',
                }
            else:
                model_data_ids = mod_obj.search(cr, uid,[('model', '=', 'ir.ui.view'), ('name', '=', 'info_start_form_view')], context=context)
                resource_id = mod_obj.read(cr, uid, model_data_ids, fields=['res_id'], context=context)[0]['res_id']
                return {
                    'name': _('Message'),
                    'context': context,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'base.module.record.objects',
                    'views': [(resource_id, 'form')],
                    'type': 'ir.actions.act_window',
                    'target': 'new',
                }
        model_data_ids = mod_obj.search(cr, uid,[('model', '=', 'ir.ui.view'), ('name', '=', 'module_recording_message_view')], context=context)
        resource_id = mod_obj.read(cr, uid, model_data_ids, fields=['res_id'], context=context)[0]['res_id']
        
        return {
            'name': _('Message'),
            'context': context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'base.module.record.objects',
            'views': [(resource_id, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'new',
        }      
        
base_module_save()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: