# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (c) 2011 OpenERP S.A. <http://openerp.com>
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

import base64
import hashlib
import json
import logging
import re
import time
import urllib2

import openerp
import openerp.release as release
from osv import osv,fields
from tools.translate import _
from tools.parse_version import parse_version

EXTERNAL_ID_PATTERN = re.compile(r'^(\S+:)?(\S+?)\.(\S+)$')

def split_external_id(ext_id):
    match = EXTERNAL_ID_PATTERN.match(ext_id)
    assert match, \
            _("'%s' is an invalid external ID") % (ext_id)
    return {'module': match.group(1) and match.group(1)[:-1],
            'db_uuid': match.group(2),
            'id': match.group(3),
            'full': match.group(0)}

def safe_unique_id(database_id, model, record_id):
    """Generate a unique string to represent a (database_uuid,model,record_id) pair
    without being too long, and with a very low probability of collisions.
    """
    msg = "%s-%s-%s-%s" % (time.time(), database_id, model, record_id)
    digest = hashlib.sha1(msg).digest()
    # fold the sha1 20 bytes digest to 9 bytes
    digest = ''.join(chr(ord(x) ^ ord(y)) for (x,y) in zip(digest[:9], digest[9:-2]))
    # b64-encode the 9-bytes folded digest to a reasonable 12 chars ASCII ID
    digest = base64.urlsafe_b64encode(digest)
    return '%s-%s' % (model.replace('.','_'), digest)

def version_tuple():
    return parse_version(release.version)

def last_update_for(record):
    """Returns the last update timestamp for the given record,
       if available, otherwise False
    """
    if record._model._log_access:
        record_log = record.perm_read()[0]
        return record_log.get('write_date') or record_log.get('create_date') or False
    return False

_logger = logging.getLogger('edi')

class edi_document(osv.osv):
    _name = 'edi.document'
    _description = 'EDI Document'
    _columns = {
                'name': fields.char("EDI token", size = 128, help="Unique identifier for retrieving an EDI document."),
                'document': fields.text("Document", help="EDI document content")
    }
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'EDI Tokens must be unique!')
    ]

    def new_edi_token(self, cr, uid, record):
        """Return a new, random unique token to identify this model record,
        and to be used as token when exporting it as an EDI document.

        :param browse_record record: model record for which a token is needed
        """
        db_uuid = self.pool.get('ir.config_parameter').get_param(cr, uid, 'database.uuid')
        edi_token = hashlib.sha256('%s-%s-%s-%s' % (time.time(), db_uuid, record._name, record.id)).hexdigest()
        return edi_token

    def serialize(self, edi_documents):
        """Serialize the given EDI document structures (Python dicts holding EDI data),
        using JSON serialization.

        :param [dict] edi_documents: list of EDI document structures to serialize
        :return: UTF-8 encoded string containing the serialized document
        """
        serialized_list = json.dumps(edi_documents)
        return serialized_list

    def generate_edi(self, cr, uid, records, context=None):
        """Generates a final EDI document containing the EDI serialization
        of the given records, which should all be instances of a Model
        that has the :meth:`~.edi` mixin. The document is not saved in the
        database, this is done by :meth:`~.export_edi`.

        :param list(browse_record) records: records to export as EDI
        :return: UTF-8 encoded string containing the serialized records
        """
        edi_list = []
        for record in records:
            record_model_obj = self.pool.get(record._name)
            edi_list += record_model_obj.edi_export(cr, uid, [record], context=context)
        return self.serialize(edi_list)

    def get_document(self, cr, uid, edi_token, context=None):
        """Retrieve the EDI document corresponding to the given edi_token.

        :return: EDI document string
        :raise: ValueError if requested EDI token does not match any know document
        """
        _logger.debug("get_document(%s)", edi_token)
        edi_ids = self.search(cr, uid, [('name','=', edi_token)], context=context)
        if not edi_ids:
            raise ValueError('Invalid EDI token: %s' % edi_token)
        edi = self.browse(cr, uid, edi_ids[0], context=context)
        return edi.document

    def load_edi(self, cr, uid, edi_documents, context=None):
        """Import the given EDI document structures into the system, using
        :meth:`~.import_edi`.

        :param edi_documents: list of Python dicts containing the deserialized
                              version of EDI documents
        :return: list of (model, id) pairs containing the model and database ID
                 of all records that were imported in the system
        """
        ir_module = self.pool.get('ir.module.module')
        res = []
        for edi_document in edi_documents:
            module = edi_document.get('__module')
            if module != 'base' and not ir_module.search(cr, uid, [('name','=',module),('state','=','installed')]):
                raise osv.except_osv(_('Missing Application'),
                            _("The document you are trying to import requires the OpenERP `%s` application. "
                              "The OpenERP configuration assistant will help with this if you are connected as an administrator.")%(module,))
            model = edi_document.get('__model')
            assert model, '__model attribute is required in each EDI document'
            model_obj = self.pool.get(model)
            record_id = model_obj.edi_import(cr, uid, edi_document, context=context)
            res.append((model, record_id))
        return res

    def deserialize(self, edi_documents_string):
        """Return deserialized version of the given EDI Document string.

        :param str|unicode edi_documents_string: UTF-8 string (or unicode) containing
                                                 JSON-serialized EDI document(s)
        :return: Python object representing the EDI document(s) (usually a list of dicts)
        """
        return json.loads(edi_documents_string)

    def export_edi(self, cr, uid, records, context=None):
        """Export the given database records as EDI documents, stores them
        permanently with a new unique EDI token, for later retrieval via :meth:`~.get_document`,
        and returns the list of the new corresponding ``ir.edi.document`` records.

        :param records: list of browse_record of any model
        :return: list of IDs of the new ``ir.edi.document`` entries, in the same
                 order as the provided ``records``.
        """
        exported_ids = []
        for record in records:
            document = self.generate_edi(cr, uid, [record], context)
            token = self.new_edi_token(cr, uid, record)
            self.create(cr, uid, {
                         'name': token,
                         'document': document
                        }, context=context)
            exported_ids.append(token)
        return exported_ids

    def import_edi(self, cr, uid, edi_document=None, edi_url=None, context=None):
        """Import a JSON serialized EDI Document string into the system, first retrieving it
        from the given ``edi_url`` if provided.

        :param str|unicode edi_document: UTF-8 string or unicode containing JSON-serialized
                                         EDI Document to import. Must not be provided if
                                         ``edi_url`` is given.
        :param str|unicode edi_url: URL where the EDI document (same format as ``edi_document``)
                                    may be retrieved, without authentication.
        """
        if edi_url:
            assert not edi_document, 'edi_document must not be provided if edi_url is given'
            edi_document = urllib2.urlopen(edi_url).read()
        assert edi_document, 'EDI Document is empty!'
        edi_documents = self.deserialize(edi_document)
        return self.load_edi(cr, uid, edi_documents, context=context)


class EDIMixin(object):
    """Mixin class for Model objects that want be exposed as EDI documents.
       Classes that inherit from this mixin class should override the
       ``edi_import()`` and ``edi_export()`` methods to implement their
       specific behavior, based on the primitives provided by this mixin."""

    # private method, not RPC-exposed as it creates ir.model.data entries as
    # SUPERUSER based on its parameters
    def _edi_external_id(self, cr, uid, record, existing_id=None, existing_module=None,
                        context=None):
        """Generate/Retrieve unique external ID for ``record``.
        Each EDI record and each relationship attribute in it is identified by a
        unique external ID, which includes the database's UUID, as a way to
        refer to any record within any OpenERP instance, without conflict.

        For OpenERP records that have an existing "External ID" (i.e. an entry in
        ir.model.data), the EDI unique identifier for this record will be made of
        "%s:%s:%s" % (module, database UUID, ir.model.data ID). The database's
        UUID MUST NOT contain a colon characters (this is guaranteed by the
        UUID algorithm).

        For records that have no existing ir.model.data entry, a new one will be
        created during the EDI export. It is recommended that the generated external ID
        contains a readable reference to the record model, plus a unique value that
        hides the database ID. If ``existing_id`` is provided (because it came from
        an import), it will be used instead of generating a new one.
        If ``existing_module`` is provided (because it came from
        an import), it will be used instead of using local values.

        :param browse_record record: any browse_record needing an EDI external ID
        :param string existing_id: optional existing external ID value, usually coming
                                   from a just-imported EDI record, to be used instead
                                   of generating a new one
        :param string existing_module: optional existing module name, usually in the
                                       format ``module:db_uuid`` and coming from a
                                       just-imported EDI record, to be used instead
                                       of local values
        :return: the full unique External ID to use for record
        """
        ir_model_data = self.pool.get('ir.model.data')
        db_uuid = self.pool.get('ir.config_parameter').get_param(cr, uid, 'database.uuid')
        ext_id = self.get_external_id(cr, uid, [record.id])[record.id]
        if not ext_id:
            ext_id = existing_id or safe_unique_id(db_uuid, record._name, record.id)
            # ID is unique cross-db thanks to db_uuid (already included in existing_module)
            module = existing_module or "%s:%s" % (record._module, db_uuid)
            _logger.debug("%s: Generating new external ID `%s.%s` for %r", self._name,
                          module, ext_id, record)
            ir_model_data.create(cr, openerp.SUPERUSER_ID,
                                 {'name': ext_id,
                                  'model': record._name,
                                  'module': module,
                                  'res_id': record.id})
        else:
            module, ext_id = ext_id.split('.')
            if not ':' in module:
                # this record was not previously EDI-imported
                assert module == record._module, 'Module mismatch between record and its current'\
                                                 'external ID'
                # ID is unique cross-db thanks to db_uuid
                module = "%s:%s" % (module, db_uuid)

        return '%s.%s' % (module, ext_id)

    def edi_metadata(self, cr, uid, records, context=None):
        """Return a list containing the boilerplate EDI structures for
           exporting ``records`` as EDI, including
           the metadata fields

        The metadata fields always include::

            {
               '__model': 'some.model',                # record model
               '__module': 'module',                   # require module
               '__id': 'module:db-uuid:model.id',      # unique global external ID for the record
               '__last_update': '2011-01-01 10:00:00', # last update date in UTC!
               '__version' : [6,1,0],                  # server version, to check compatibility.
               '__attachments_':
           }

        :param list(browse_record) records: records to export
        :return: list of dicts containing boilerplate EDI metadata for each record,
                 at the corresponding index from ``records``.
        """
        data_ids = []
        ir_attachment = self.pool.get('ir.attachment')
        results = []
        version = version_tuple()
        for record in records:
            attachment_ids = ir_attachment.search(cr, uid, [('res_model','=', record._name), ('res_id', '=', record.id)])
            attachments = []
            for attachment in ir_attachment.browse(cr, uid, attachment_ids, context=context):
                attachments.append({
                        'name' : attachment.name,
                        'content': attachment.datas, # already base64 encoded!
                        'file_name': attachment.datas_fname,
                })
            ext_id = self._edi_external_id(cr, uid, record, context=context)
            edi_dict = {
                '__id': ext_id,
                '__last_update': last_update_for(record),
                '__model' : record._name,
                '__module' : record._module,
                '__version': version,
                '__attachments': attachments,
            }
            results.append(edi_dict)
        return results

    def edi_m2o(self, cr, uid, record, context=None):
        """Return a m2o EDI representation for the given record.

        The EDI format for a many2one is::

            ['unique_external_id', 'Document Name']
        """
        edi_ext_id = self._edi_external_id(cr, uid, record, context=context)
        relation_model = record._model
        name = relation_model.name_get(cr, uid, [record.id], context=context)
        name = name and name[0][1] or False
        return [edi_ext_id, name]

    def edi_o2m(self, cr, uid, records, edi_struct=None, context=None):
        """Return a list representing a O2M EDI relationship containing
           all the given records, according to the given ``edi_struct``.
           This is basically the same as exporting all the record using
           :meth:`~.edi_export` with the given ``edi_struct``, and wrapping
           the results in a list.

           Example::

             [                                # O2M fields would be a list of dicts, with their
               { '__id': 'module:db-uuid.id', # own __id.
                 '__last_update': 'iso date', # update date
                 'name': 'some name',
                 #...
               },
               # ...
             ],
        """
        result = []
        for record in records:
            result += record._model.edi_export(cr, uid, [record], edi_struct=edi_struct, context=context)
        return result

    def edi_m2m(self, cr, uid, records, context=None):
        """Return a list representing a M2M EDI relationship directed towards
           all the given records.
           This is basically the same as exporting all the record using
           :meth:`~.edi_m2o` and wrapping the results in a list.

            Example::

                # M2M fields are exported as a list of pairs, like a list of M2O values
                [
                      ['module:db-uuid.id1', 'Task 01: bla bla'],
                      ['module:db-uuid.id2', 'Task 02: bla bla']
                ]
        """
        return [self.edi_m2o(cr, uid, r, context=context) for r in records]

    def edi_export(self, cr, uid, records, edi_struct=None, context=None):
        """Returns a list of dicts representing an edi.document containing the
           records, and matching the given ``edi_struct``, if provided.

           :param edi_struct: if provided, edi_struct should be a dictionary
                              with a skeleton of the fields to export.
                              Basic fields can have any key as value, but o2m
                              values should have a sample skeleton dict as value,
                              to act like a recursive export.
                              For example, for a res.partner record::

                                  edi_struct: {
                                       'name': True,
                                       'company_id': True,
                                       'address': {
                                           'name': True,
                                           'street': True,
                                           }
                                  }

                              Any field not specified in the edi_struct will not
                              be included in the exported data. Fields with no
                              value (False) will be omitted in the EDI struct.
                              If edi_struct is omitted, no fields will be exported
        """
        if edi_struct is None:
            edi_struct = {}
        fields_to_export = edi_struct.keys()
        results = []
        for record in records:
            edi_dict = self.edi_metadata(cr, uid, [record], context=context)[0]
            for field in fields_to_export:
                column = self._all_columns[field].column
                value = getattr(record, field)
                if not value:
                    continue
                #if _fields[field].has_key('function') or _fields[field].has_key('related_columns'):
                #    # Do not Export Function Fields and related fields
                #    continue
                elif column._type == 'many2one':
                    value = self.edi_m2o(cr, uid, value, context=context)
                elif column._type == 'many2many':
                    value = self.edi_m2m(cr, uid, value, context=context)
                elif column._type == 'one2many':
                    value = self.edi_o2m(cr, uid, value, edi_struct=edi_struct.get(field, {}), context=context)
                edi_dict[field] = value
            results.append(edi_dict)
        return results

    def _edi_get_object_by_name(self, cr, uid, name, model_name, context=None):
        model = self.pool.get(model_name)
        search_results = model.name_search(cr, uid, name, operator='=', context=context)
        if len(search_results) == 1:
            return model.browse(cr, uid, search_results[0][0], context=context)
        return False

    def _edi_import_attachments(self, cr, uid, record_id, edi_document, context=None):
        ir_attachment = self.pool.get('ir.attachment')
        for attachment in edi_document.get('__attachments', []):
            # check attachment data is non-empty and valid
            file_data = None
            try:
                file_data = base64.b64decode(attachment.get('content'))
            except TypeError:
                pass
            assert file_data, 'Incorrect/Missing attachment file content'
            assert attachment.get('name'), 'Incorrect/Missing attachment name'
            assert attachment.get('file_name'), 'Incorrect/Missing attachment file name'
            assert attachment.get('file_name'), 'Incorrect/Missing attachment file name'
            ir_attachment.create(cr, uid, {'name': attachment['name'],
                                           'datas_fname': attachment['file_name'],
                                           'res_model': self._name,
                                           'res_id': record_id,
                                           # should be pure 7bit ASCII
                                           'datas': str(attachment['content']),
                                           }, context=context)


    def _edi_get_object_by_external_id(self, cr, uid, external_id, model, context=None):
        """Returns browse_record representing object identified by the model and external_id,
           or None if no record was found with this external id.

           :param external_id: fully qualified external id, in the EDI form
                               ``module:db_uuid:identifier``.
           :param model: model name the record belongs to.
        """
        ir_model_data = self.pool.get('ir.model.data')
        # external_id is expected to have the form: ``module:db_uuid:model.random_name``
        ext_id_members = split_external_id(external_id)
        db_uuid = self.pool.get('ir.config_parameter').get_param(cr, uid, 'database.uuid')
        module = ext_id_members['module']
        ext_id = ext_id_members['id']
        ext_module = '%s:%s' % (module, ext_id_members['db_uuid'])
        data_ids = ir_model_data.search(cr, uid, [('model','=',model),
                                                  ('name','=',ext_id),
                                                  ('module','in',[ext_module,module])])
        if data_ids:
            model = self.pool.get(model)
            data = ir_model_data.browse(cr, uid, data_ids[0], context=context)
            result = model.browse(cr, uid, data.res_id, context=context)
            return result

    def edi_import_relation(self, cr, uid, model, value, external_id, context=None):
        """Imports a M2O/M2M relation EDI specification ``[external_id,value]`` for the
           given model, returning the corresponding database ID:

           * First, checks if the ``external_id`` is already known, in which case the corresponding
             database ID is directly returned, without doing anything else;
           * If the ``external_id`` is unknown, attempts to locate an existing record
             with the same ``value`` via name_search(). If found, the given external_id will
             be assigned to this local record (in addition to any existing one)
           * If previous steps gave no result, create a new record with the given
             value in the target model, assign it the given external_id, and return
             the new database ID
        """
        _logger.debug("%s: Importing EDI relationship [%r,%r]", self._name, external_id, value)
        target = self._edi_get_object_by_external_id(cr, uid, external_id, model, context=context)
        need_new_ext_id = False
        if not target:
            _logger.debug("%s: Importing EDI relationship [%r,%r] - ID not found, trying name_get",
                          self._name, external_id, value)
            target = self._edi_get_object_by_name(cr, uid, value, model, context=context)
            need_new_ext_id = True
        if not target:
            _logger.debug("%s: Importing EDI relationship [%r,%r] - name not found, creating it!",
                          self._name, external_id, value)
            # also need_new_ext_id here, but already been set above
            res_id, name = self.name_create(cr, uid, value, context=context)
            target = model.browse(cr, uid, res_id, context=context)
        if need_new_ext_id:
            ext_id_members = split_external_id(external_id)
            # module name is never used bare when creating ir.model.data entries, in order
            # to avoid being taken as part of the module's data, and cleanup up at next update  
            module = "%s:%s" % (ext_id_members['module'], ext_id_members['db_uuid'])
            # create a new ir.model.data entry for this value
            self._edi_external_id(cr, uid, target, existing_id=ext_id_members['id'], existing_module=module, context=context)
        return target.id

    def edi_import(self, cr, uid, edi_document, context=None):
        """Imports a dict representing an edi.document into the system,
           applying the following rules.

           All relationship fields are exported in a special way, and provide their own
           unique identifier, so that we can avoid duplication of records when importing.

           #. Many2One
               See :meth:`~.edi_import_relation`

           #. One2Many
               O2M fields are always exported as a list of dicts, where each dict corresponds
               to a full EDI record. The import should not update existing records
               if they already exist, it should only link them to the parent object, in this
               fashion:
                   * First import the parent object, using the usual procedire
                   * Look for a record that matches the db_id provided in the __id field. If
                     found, keep the corresponding database id, and connect it to the parent.
                   * If not found via db_id, create a new entry using the same method that
                     imports a full EDI record, grab the resulting db id, and use it to
                     connect to the parent.

           #: Many2Many
               M2M fields are always exported as a list of pairs similar to M2O.
               For each pair in the M2M:
                   * Perform the same steps as for a Many2One (See :meth:`~.edi_import_relation`)
                   * After finding the database ID of the final record in the database,
                     connect it to the parent record.
        """
        assert self._name == edi_document['__model'],\
              "EDI Document Model and current model do not match: '%s' (EDI) vs '%s' (current)" % \
                (edi_document['__model'], self._name)

        # First check the record is now already known in the database, in which case it is ignored
        ext_id_members = split_external_id(edi_document['__id'])
        existing_id = self._edi_get_object_by_external_id(cr, uid, ext_id_members['full'], self._name, context=context)
        if existing_id:
            _logger.info("'%s' EDI Document with ID '%s' is already known, skipping import!", self._name, ext_id_members['full'])
            return

        record_values = {}
        o2m_todo = {} # o2m values are processed after their parent already exists
        for field_name, field_value in edi_document.iteritems():
            # skip metadata and empty fields
            if field_name.startswith('__') or field_value is None or field_value is False:
                continue
            field = self._all_columns[field_name].column
            # skip function/related fields
            if isinstance(field, fields.function):
                _logger.warning("Unexpected function field value found in '%s' EDI document: '%s'" % (self._name, field_name))
                continue
            relation_model = field._obj
            if field._type == 'many2one':
                record_values[field_name] = self.edi_import_relation(cr, uid, relation_model,
                                                                      field_value[1], field_value[0],
                                                                      context=context)
            elif field._type == 'many2many':
                record_values[field_name] = [self.edi_import_relation(cr, uid, relation_model, m2m_value[1],
                                                                       m2m_value[0], context=context)
                                             for m2m_value in field_value]
            elif field._type == 'one2many':
                # must wait until parent report is imported, as the parent relationship
                # is often required in o2m child records
                o2m_todo[field_name] = field_value
            else:
                record_values[field_name] = field_value

        module_ref = "%s:%s" % (ext_id_members['module'], ext_id_members['db_uuid'])
        record_id = self.pool.get('ir.model.data')._update(cr, uid, self._name, module_ref, record_values,
                                                           xml_id=ext_id_members['id'], context=context)

        record_display, = self.name_get(cr, uid, [record_id], context=context)

        # process o2m values, connecting them to their parent on-the-fly
        for o2m_field, o2m_value in o2m_todo.iteritems():
            field = self._all_columns[o2m_field].column
            dest_model = self.pool.get(field._obj)
            for o2m_line in o2m_value:
                # link to parent record: expects an (ext_id, name) pair
                o2m_line[field._fields_id] = (ext_id_members['full'], record_display[1])
                dest_model.edi_import(cr, uid, o2m_line, context=context)

        # process the attachments, if any
        self._edi_import_attachments(cr, uid, record_id, edi_document, context=context)

        return record_id

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: