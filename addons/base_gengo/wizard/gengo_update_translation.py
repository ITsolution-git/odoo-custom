# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (C) 2004-2012 OpenERP S.A. (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv
from tools.translate import _
import re
try:
    from mygengo import MyGengo
except ImportError:
    raise osv.except_osv(_('Gengo ImportError'), _('Please install mygengo lib from http://pypi.python.org/pypi/mygengo'))

import logging
import tools
import time

_logger = logging.getLogger(__name__)

GENGO_DEFAULT_LIMIT = 20

LANG_CODE_MAPPING = {
    'ar_SA': ('ar', 'Arabic'),
    'id_ID': ('id', 'Indonesian'),
    'nl_NL': ('nl', 'Dutch'),
    'fr_CA': ('fr-ca', 'French (Canada)'),
    'pl_PL': ('pl', 'Polish'),
    'zh_TW': ('zh-tw', 'Chinese (Traditional)'),
    'sv_SE': ('sv', 'Swedish'),
    'ko_KR': ('ko', 'Korean'),
    'pt_PT': ('pt', 'Portuguese (Europe)'),
    'en_US': ('en', 'English'),
    'ja_JP': ('ja', 'Japanese'),
    'es_ES': ('es', 'Spanish (Spain)'),
    'zh_CN': ('zh', 'Chinese (Simplified)'),
    'de_DE': ('de', 'German'),
    'fr_FR': ('fr', 'French'),
    'fr_BE': ('fr', 'French'),
    'ru_RU': ('ru', 'Russian'),
    'it_IT': ('it', 'Italian'),
    'pt_BR': ('pt-br', 'Portuguese (Brazil)')
}

CRON_VALS = {
    'name': _('Synchronization with Gengo'),
    'active': True,
    'interval_number': 20,
    'interval_type': 'minutes',
    'numbercall': -1,
    'model': "'base.update.translations'",
    'function': "",
    'args': "'(20,)'",#not sure
}


class base_update_translation(osv.osv_memory):

    _name = 'base.update.translations'
    _inherit = "base.update.translations"

    def gengo_authentication(self, cr, uid, context=None):
        ''' To Send Request and Get Response from Gengo User needs Public and Private
         key for that user need to sign up to gengo and get public and private
         key which is provided by gengo to authenticate user '''

        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if not user.company_id.gengo_public_key or not user.company_id.gengo_private_key:
            return (False, _("  - Invalid Gengo configuration. Gengo authentication `Public Key` or `Private Key` is missing. Complete Gengo authentication parameters under `Settings > Companies > Gengo Parameters`."))
        try:
            gengo = MyGengo(
                public_key=user.company_id.gengo_public_key.encode('ascii'),
                private_key=user.company_id.gengo_private_key.encode('ascii'),
                sandbox=True,
            )
            gengo.getAccountStats()
            return (True, gengo)
        except Exception, e:
            return (False, _("Gengo Connection Error\n%s") %e)

    def pack_jobs_request(self, cr, uid, term_ids, context=None):
        ''' prepare the terms that will be requested to gengo and returns them in a dictionary with following format
            {'jobs': {
                'term1.id': {...}
                'term2.id': {...}
                }
            }'''

        translation_pool = self.pool.get('ir.translation')
        jobs = {}
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        auto_approve = 1 if user.company_id.gengo_auto_approve or 0
        for term in translation_pool.browse(cr, uid, term_ids, context=context):
            if re.search(r"\w", term.src or ""):
                jobs[term.id] = {'type': 'text',
                        'slug': 'single::English to ' + LANG_CODE_MAPPING[term.lang][1],
                        'tier': tools.ustr(user.company_id.gengo_tier),
                        #'tier': tools.ustr(term.gengo_tier),
                        'body_src': term.src,
                        'lc_src': 'en',
                        'lc_tgt': LANG_CODE_MAPPING[term.lang][0],
                        'auto_approve': auto_approve,
                        'comment': gengo_parameter_pool.company_id.gengo_comment,
                }
        return {'jobs': jobs}

    def check_lang_support(self, cr, uid, langs, context=None):
        new_langs = []
        flag, gengo = self.gengo_authentication(cr, uid, context)
        if not flag:
            return []
        else:
            user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
            tier = user.company_id.gengo_tier
            if tier == "machine":
                tier = "nonprofit"
            lang_pair = gengo.getServiceLanguagePairs(lc_src='en')
            #print "tier", tier

            if lang_pair['opstat'] == 'ok':
                for g_lang in lang_pair['response']:
                     #print 'g_lang', g_lang['lc_tgt'], g_lang['tier']
                    for l in langs:
                        if LANG_CODE_MAPPING[l][0] == g_lang['lc_tgt'] and g_lang['tier'] == tier:
                            new_langs.append(l)
            return list(set(new_langs))

    def _update_terms(self, cr, uid, response, tier, context=None):
        translation_pool = self.pool.get('ir.translation')
        for jobs in response['jobs']:
            for t_id, res in jobs.items():
                vals = {}
                if tier == "machine":
                    vals.update({'value': res['body_tgt'], 'state': 'translated'})
                else:
                    vals.update({'job_id': res['job_id'], 'state': 'inprogress'})
                translation_pool.write(cr, uid, [t_id], vals, context=context)
        return

    def _send_translation_terms(self, cr, uid,  term_ids, context=None):
        """
        Lazy Polling will be perform when user or cron request for the translation.
        """
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        flag, gengo = self.gengo_authentication(cr, uid, context)
        if flag:
            request = self.pack_jobs_request(cr, uid, term_ids, context)
            if request['jobs']:
                result = gengo.postTranslationJobs(jobs=request)
                if result['opstat'] == 'ok':
                    self._update_terms(cr, uid, result['response'], user.company_id.gengo_tier, context)
        else:
            _logger.error(gengo)
        return True

    def do_check_schedular(self, cr, uid, xml_id, name, fn, context=None):
        cron_pool = self.pool.get('ir.cron')
        try:
            res = []
            model, res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base_gengo', xml_id)
            cron_pool.write(cr, uid, [res], {'active': True}, context=context)
        except:
            CRON_VALS.update({'name': name, "function": fn})
            return cron_pool.create(cr, uid, CRON_VALS, context)

    def act_update(self, cr, uid, ids, context=None):
        if context == None:
            context = {}
        lang_pool = self.pool.get('res.lang')
        super(base_update_translation, self).act_update(cr, uid, ids, context)
        msg = _("1. Translation file loaded successfully.\n2. Processing Gengo Translation:\n")
        flag, gengo = self.gengo_authentication(cr, uid, context)
        if not flag:
            msg += gengo
        else:
            for res in self.browse(cr, uid, ids, context=context):
                lang_id = lang_pool.search(cr, uid, [('code', '=', res.lang)])
                lang_name = self._get_lang_name(cr, uid, res.lang)
                try:
                    if LANG_CODE_MAPPING[res.lang][0]:
                        lang_search = lang_pool.search(cr, uid, [('gengo_sync', '=', True), ('id', '=', lang_id[0])])
                    if lang_search:
                        msg += _('  - This language `%s` is already in queue for translation.') % (lang_name)
                    else:
                        msg += _('  - The language `%s` is queued for translation through Gengo translation.') % (lang_name)
                        lang_pool.write(cr, uid, lang_id, {'gengo_sync': True})
                        _logger.info('Translation request for language `%s` has been queued successfully.', lang_name)
                    self.do_check_schedular(cr, uid, 'gengo_sync_send_request_scheduler', _('Gengo Sync Translation (Request)'), '_sync_request', context)
                    self.do_check_schedular(cr, uid, 'gengo_sync_receive_request_scheduler', _('Gengo Sync Translation (Response)'), '_sync_response', context)
                    self._sync_request(cr, uid, limit=GENGO_DEFAULT_LIMIT)
                except:
                    msg += _('  - The Language `%s` is not supported by Gengo Traditional Service.') % (lang_name)

        obj_model = self.pool.get('ir.model.data')
        model_data_ids = obj_model.search(cr, uid, [('model', '=', 'ir.ui.view'), ('name', '=', 'update_translation_wizard_view_confirm')])
        view_id = obj_model.read(cr, uid, model_data_ids, fields=['res_id'], context=context)[0]['res_id']
        context.update({'message': msg})
        return {
                 'view_type': 'form',
                 'view_mode': 'form',
                 'res_model': 'gengo.update.message',
                 'views': [(view_id, 'form')],
                 'type': 'ir.actions.act_window',
                 'target': 'new',
                 'context': context,
             }

    def _sync_response(self, cr, uid, limit=GENGO_DEFAULT_LIMIT, context=None):
        """
        This method  will be call by cron services to get translation from
        gengo for translation terms which are posted to be translated. It will
        read translated terms and comments from gengo and will update respective
        translation in openerp.
        """
        translation_pool = self.pool.get('ir.translation')
        flag, gengo = self.gengo_authentication(cr, uid, context)
        if not flag:
            _logger.warning("%s", gengo)
        else:
            translation_id = translation_pool.search(cr, uid, [('state', '=', 'inprogress'), ('gengo_translation', '=', True)], limit=limit, context=context)
            for term in translation_pool.browse(cr, uid, translation_id, context):
                up_term = up_comment = 0
                if term.job_id:
                    vals={}
                    job_response = gengo.getTranslationJob(id=term.job_id)
                    if job_response['opstat'] != 'ok':
                        _logger.warning("Invalid Response! Skipping translation Terms with `id` %s." % (term.job_id))
                        continue
                    if job_response['response']['job']['status'] == 'approved':
                        vals.update({'state': 'translated',
                            'value': job_response['response']['job']['body_tgt'],
                            'gengo_control': True})
                        up_term += 1
                    job_comment = gengo.getTranslationJobComments(id=term.job_id)
                    if job_comment['opstat']=='ok':
                        gengo_comments=""
                        for comment in job_comment['response']['thread']:
                            gengo_comments += _('%s Commented on %s by %s. \n') %(comment['body'], time.ctime(comment['ctime']), comment['author'])
                        vals.update({'gengo_comment': gengo_comments})
                        up_comment +=1
                    if vals:
                        translation_pool.write(cr, uid, term.id,vals)
                    _logger.info("Successfully Updated `%d` terms and Comments for `%d` terms." % (up_term, up_comment ))
        return True

    def _sync_request(self, cr, uid, limit=GENGO_DEFAULT_LIMIT, context=None):
        """This scheduler will send a job request to the gengo , which terms are
        waiing to be translated and for which gengo_translation is True"""
        if context is None:
            context = {}
        language_pool = self.pool.get('res.lang')
        translation_pool = self.pool.get('ir.translation')
        try:
            lang_ids = language_pool.search(cr, uid, [('gengo_sync', '=', True)]) #really? what's the point not checking ALL the languages if gengo support it? i feel like it's aunecessary load for the user that must configure yet another thing
            langs = [lang.code for lang in language_pool.browse(cr, uid, lang_ids, context=context)]
            #print "LANGS 1", langs
            langs = self.check_lang_support(cr, uid, langs, context=context)#must move
            #print "LANGS 2", langs
            term_ids = translation_pool.search(cr, uid, [('state', '=', 'to_translate'), ('gengo_translation', '=', True), ('lang', 'in', langs)], limit=limit)
            if term_ids:
                self._send_translation_terms(cr, uid, term_ids, context)
                _logger.info("Translation terms %s has been posted to gengo successfully", len(term_ids))
            else:
                _logger.info('No Translation terms to process.')
        except Exception, e:
            _logger.error("%s", e)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
