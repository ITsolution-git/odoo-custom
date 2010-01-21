# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
import datetime
from time import strftime
import datetime
import copy
from tools.translate import _
from lxml import etree
from tools import to_xml
import tools

class survey(osv.osv):
    _name = 'survey'
    _description = 'Survey'
    _rec_name = 'title'
    _columns = {
        'title' : fields.char('Survey Title', size=128, required=1),
        'page_ids' : fields.one2many('survey.page', 'survey_id', 'Page'),
        'date_open' : fields.datetime('Survey Open Date', readonly=1),
        'date_close' : fields.datetime('Survey Close Date', readonly=1),
        'max_response_limit' : fields.integer('Maximum Response Limit'),
        'response_user' : fields.integer('Maximum Response per User',
                     help="Set to one if  you require only one response per user"),
        'state' : fields.selection([('draft', 'Draft'), ('open', 'Open'), ('close', 'Closed'), ('cancel', 'Cancelled')], 'Status', readonly=True),
        'responsible_id' : fields.many2one('res.users', 'Responsible'),
        'tot_start_survey' : fields.integer("Total Started Survey", readonly=1),
        'tot_comp_survey' : fields.integer("Total Completed Survey", readonly=1),
        'note' : fields.text('Description', size=128),
        'history' : fields.one2many('survey.history', 'survey_id', 'History Lines', readonly=True),
        'users': fields.many2many('res.users', 'survey_users_rel', 'sid', 'uid', 'Users'),
        'question_prefix' : fields.char('Question Prefix', size=128),
    }
    _defaults = {
        'state' : lambda * a: "draft",
        'tot_start_survey' : lambda * a: 0,
        'tot_comp_survey' : lambda * a: 0,
    }

    def survey_draft(self, cr, uid, ids, arg):
        self.write(cr, uid, ids, { 'state' : 'draft'})
        return True

    def survey_open(self, cr, uid, ids, arg):
        self.write(cr, uid, ids, { 'state' : 'open', 'date_open':strftime("%Y-%m-%d %H:%M:%S")})
        return True

    def survey_close(self, cr, uid, ids, arg):
        self.write(cr, uid, ids, { 'state' : 'close', 'date_close':strftime("%Y-%m-%d %H:%M:%S") })
        return True

    def survey_cancel(self, cr, uid, ids, arg):
        self.write(cr, uid, ids, { 'state' : 'cancel' })
        return True

survey()

class survey_history(osv.osv):
    _name = 'survey.history'
    _description = 'Survey History'
    _rec_name = 'date'
    _columns = {
        'survey_id' : fields.many2one('survey', 'Survey'),
        'user_id' : fields.many2one('res.users', 'User', readonly=True),
        'date' : fields.datetime('Date started', readonly=1),
    }
    _defaults = {
         'date' : lambda * a: datetime.datetime.now()
    }

survey_history()

class survey_page(osv.osv):
    _name = 'survey.page'
    _description = 'Survey Pages'
    _rec_name = 'title'
    _order = 'sequence'
    _columns = {
        'title' : fields.char('Page Title', size=128, required=1),
        'survey_id' : fields.many2one('survey', 'Survey', ondelete='cascade'),
        'question_ids' : fields.one2many('survey.question', 'page_id', 'Question'),
        'sequence' : fields.integer('Page Nr'),
        'note' : fields.text('Description'),
    }
    _defaults = {
        'sequence' : lambda * a: 1
    }

    def default_get(self, cr, uid, fields, context={}):
        data = super(survey_page, self).default_get(cr, uid, fields, context)
        if context.has_key('line_order') and context['line_order']:
            if len(context['line_order'][-1]) > 2 and context['line_order'][-1][2].has_key('sequence'):
                data['sequence'] = context['line_order'][-1][2]['sequence'] + 1
        if context.has_key('survey_id'):
            data['survey_id'] = context['survey_id']
        return data

    def survey_save(self, cr, uid, ids, context):
        search_obj = self.pool.get('ir.ui.view')
        search_id = search_obj.search(cr,uid,[('model','=','survey.question.wiz'),('name','=','Survey Search')])
        surv_name_wiz = self.pool.get('survey.name.wiz')
        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'transfer':True, 'page_no' : context['page_number'] })
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.question.wiz',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'search_view_id':search_id[0],
                'context': context
                }

survey_page()

class survey_question(osv.osv):
    _name = 'survey.question'
    _description = 'Survey Question'
    _rec_name = 'question'
    _order = 'sequence'

    def _calc_response(self, cr, uid, ids, field_name, arg, context):
        if len(ids) == 0:
            return {}
        val = {}
        cr.execute("select question_id, count(id) as Total_response from survey_response_line where state='done' and question_id in (%s) group by question_id" % ",".join(map(str, map(int, ids))))
        ids1 = copy.deepcopy(ids)
        for rec in  cr.fetchall():
            ids1.remove(rec[0])
            val[rec[0]] = int(rec[1])
        for id in ids1:
            val[id] = 0
        return val

    _columns = {
        'page_id' : fields.many2one('survey.page', 'Survey Page', ondelete='cascade', required=1),
        'question' :  fields.char('Question', size=128, required=1),
        'answer_choice_ids' : fields.one2many('survey.answer', 'question_id', 'Answer'),
        'response_ids' : fields.one2many('survey.response.line', 'question_id', 'Response', readonly=1),
        'is_require_answer' : fields.boolean('Required Answer'),
        'required_type' : fields.selection([('',''), ('all','All'), ('at least','At Least'), ('at most','At Most'), ('exactly','Exactly'), ('a range','A Range')], 'Respondent must answer'),
        'req_ans' : fields.integer('#Required Answer'),
        'maximum_req_ans' : fields.integer('Maximum Required Answer'),
        'minimum_req_ans' : fields.integer('Minimum Required Answer'),
        'req_error_msg' : fields.text('Error Message'),
        'allow_comment' : fields.boolean('Allow Comment Field'),
        'sequence' : fields.integer('Sequence'),
        'tot_resp' : fields.function(_calc_response, method=True, string="Total Response"),
        'survey' : fields.related('page_id', 'survey_id', type='many2one', relation='survey', string='Survey'),
        'descriptive_text' : fields.text('Descriptive Text', size=255),
        'column_heading_ids' : fields.one2many('survey.question.column.heading', 'question_id',' Column heading'),
        'type' : fields.selection([('multiple_choice_only_one_ans','Multiple Choice (Only One Answer)'),
                                     ('multiple_choice_multiple_ans','Multiple Choice (Multiple Answer)'),
                                     ('matrix_of_choices_only_one_ans','Matrix of Choices (Only One Answers Per Row)'),
                                     ('matrix_of_choices_only_multi_ans','Matrix of Choices (Multiple Answers Per Row)'),
                                     ('matrix_of_drop_down_menus','Matrix of Drop-down Menus'),
                                     ('rating_scale','Rating Scale'),('single_textbox','Single Textbox'),
                                     ('multiple_textboxes','Multiple Textboxes'),('comment','Comment/Essay Box'),
                                     ('numerical_textboxes','Numerical Textboxes'),('date','Date'),
                                     ('date_and_time','Date and Time'),('descriptive_text','Descriptive Text'),
                                     ('table','Table'),
                                    ], 'Question Type',  required=1,),
        'comment_label' : fields.char('Field Label', size = 255),
        'comment_field_type' : fields.selection([('',''),('char', 'Single Line Of Text'), ('text', 'Paragraph of Text')], 'Comment Field Type'),
        'comment_valid_type' : fields.selection([('do_not_validate', '''Don't Validate Comment Text.'''),
                                                 ('must_be_specific_length', 'Must Be Specific Length'),
                                                 ('must_be_whole_number', 'Must Be A Whole Number'),
                                                 ('must_be_decimal_number', 'Must Be A Decimal Number'),
                                                 ('must_be_date', 'Must Be A Date'),
                                                 ('must_be_email_address', 'Must Be An Email Address'),
                                                 ], 'Text Validation'),
        'comment_minimum_no' : fields.integer('Minimum number'),
        'comment_maximum_no' : fields.integer('Maximum number'),
        'comment_minimum_float' : fields.float('Minimum decimal number'),
        'comment_maximum_float' : fields.float('Maximum decimal number'),
        'comment_minimum_date' : fields.date('Minimum date'),
        'comment_maximum_date' : fields.date('Maximum date'),
        'comment_valid_err_msg' : fields.text('Error message'),
        'make_comment_field' : fields.boolean('Make Comment Field an Answer Choice'),
        'make_comment_field_err_msg' : fields.text('Error message'),
        'validation_type' : fields.selection([('do_not_validate', '''Don't Validate Comment Text.'''),\
                                                 ('must_be_specific_length', 'Must Be Specific Length'),\
                                                 ('must_be_whole_number', 'Must Be A Whole Number'),\
                                                 ('must_be_decimal_number', 'Must Be A Decimal Number'),\
                                                 ('must_be_date', 'Must Be A Date'),\
                                                 ('must_be_email_address', 'Must Be An Email Address')\
                                                 ], 'Text Validation'),
        'validation_minimum_no' : fields.integer('Minimum number'),
        'validation_maximum_no' : fields.integer('Maximum number'),
        'validation_minimum_float' : fields.float('Minimum decimal number'),
        'validation_maximum_float' : fields.float('Maximum decimal number'),
        'validation_minimum_date' : fields.date('Minimum date'),
        'validation_maximum_date' : fields.date('Maximum date'),
        'validation_valid_err_msg' : fields.text('Error message'),
        'numeric_required_sum' : fields.integer('Sum of all choices'),
        'numeric_required_sum_err_msg' : fields.text('Error message'),
        'rating_allow_one_column_require' : fields.boolean('Allow Only One Response per Column (Forced Ranking)'),
        'in_visible_rating_weight':fields.boolean('Is Rating Scale Invisible?'),
        'in_visible_menu_choice':fields.boolean('Is Menu Choice Invisible?'),
        'comment_column':fields.boolean('Add comment column in matrix'),
        'column_name':fields.char('Column Name',size=256),
        'no_of_rows' : fields.integer('No of Rows'),
    }
    _defaults = {
         'sequence' : lambda * a: 1,
         'type' : lambda * a: 'multiple_choice_multiple_ans',
         'req_error_msg' : lambda * a: 'This question requires an answer.',
         'required_type' : lambda * a: '',
         'comment_label' : lambda * a: 'Other',
         'comment_valid_type' : lambda * a: 'do_not_validate',
         'comment_valid_err_msg' : lambda * a : 'The comment you entered is in an invalid format.',
         'validation_type' : lambda * a: 'do_not_validate',
         'validation_valid_err_msg' : lambda * a : 'The comment you entered is in an invalid format.',
         'numeric_required_sum_err_msg' : lambda * a :'The choices need to add up to [enter sum here].',
         'make_comment_field_err_msg' : lambda * a : 'Please enter a comment.',
    }

    def on_change_type(self, cr, uid, ids, type, context=None):
        if type in ['rating_scale']:
            return {'value': {'in_visible_rating_weight':False,'in_visible_menu_choice':True}}
        elif type in ['matrix_of_drop_down_menus']:
            return {'value': {'in_visible_rating_weight':True,'in_visible_menu_choice':False}}
        elif type in ['single_textbox']:
            return {'value': {'in_visible_rating_weight':True,'in_visible_menu_choice':True}}
        else:
            return {'value': {'in_visible_rating_weight':True,'in_visible_menu_choice':True}}

    def write(self, cr, uid, ids, vals, context=None):
        questions = self.read(cr,uid, ids, ['answer_choice_ids', 'type', 'required_type','req_ans', 'minimum_req_ans', 'maximum_req_ans', 'column_heading_ids'])
        for question in questions:
            col_len = len(question['column_heading_ids'])
            if vals.has_key('column_heading_ids'):
                for col in vals['column_heading_ids']:
                    if type(col[2]) == type({}):
                        col_len += 1
                    else:
                        col_len -= 1
            if vals.has_key('type'):
                que_type = vals['type']
            else:
                que_type = question['type']
            if que_type in ['matrix_of_choices_only_one_ans', 'matrix_of_choices_only_multi_ans', 'matrix_of_drop_down_menus', 'rating_scale']:
                if not col_len:
                    raise osv.except_osv(_('Error !'),_("You must enter one or more column heading."))
            ans_len = len(question['answer_choice_ids'])
            if vals.has_key('answer_choice_ids'):
                for ans in vals['answer_choice_ids']:
                    if type(ans[2]) == type({}):
                        ans_len += 1
                    else:
                        ans_len -= 1
            if que_type not in ['descriptive_text', 'single_textbox', 'comment','table']:
                if not ans_len:
                    raise osv.except_osv(_('Error !'),_("You must enter one or more Answer."))
            req_type = ""
            if vals.has_key('required_type'):
                req_type = vals['required_type']
            else:
                req_type = question['required_type']
            if req_type in ['at least', 'at most', 'exactly']:
                if vals.has_key('req_ans'):
                    if not vals['req_ans'] or  vals['req_ans'] > ans_len:
                        raise osv.except_osv(_('Error !'),_("#Required Answer you entered is greater than the number of answer. Please use a number that is smaller than %d.") % (ans_len + 1))
                else:
                    if not question['req_ans'] or  question['req_ans'] > ans_len:
                        raise osv.except_osv(_('Error !'),_("#Required Answer you entered is greater than the number of answer. Please use a number that is smaller than %d.") % (ans_len + 1))
            if req_type == 'a range':
                minimum_ans = 0
                maximum_ans = 0
                if vals.has_key('minimum_req_ans'):
                    minimum_ans = vals['minimum_req_ans']
                    if not vals['minimum_req_ans'] or  vals['minimum_req_ans'] > ans_len:
                        raise osv.except_osv(_('Error !'),_("Minimum Required Answer you entered is greater than the number of answer. Please use a number that is smaller than %d.") % (ans_len + 1))
                else:
                    minimum_ans = question['minimum_req_ans']
                    if not question['minimum_req_ans'] or  question['minimum_req_ans'] > ans_len:
                        raise osv.except_osv(_('Error !'),_("Minimum Required Answer you entered is greater than the number of answer. Please use a number that is smaller than %d.") % (ans_len + 1))
                if vals.has_key('maximum_req_ans'):
                    maximum_ans = vals['maximum_req_ans']
                    if not vals['maximum_req_ans'] or vals['maximum_req_ans'] > ans_len:
                        raise osv.except_osv(_('Error !'),_("Maximum Required Answer you entered for your maximum is greater than the number of answer. Please use a number that is smaller than %d.") % (ans_len + 1))
                else:
                    maximum_ans = question['maximum_req_ans']
                    if not question['maximum_req_ans'] or question['maximum_req_ans'] > ans_len:
                        raise osv.except_osv(_('Error !'),_("Maximum Required Answer you entered for your maximum is greater than the number of answer. Please use a number that is smaller than %d.") % (ans_len + 1))
                if maximum_ans <= minimum_ans:
                    raise osv.except_osv(_('Error !'),_("Maximum Required Answer is greater than Minimum Required Answer"))
            if question['type'] ==  'matrix_of_drop_down_menus' and vals.has_key('column_heading_ids'):
                for col in vals['column_heading_ids']:
                    if col[2].has_key('menu_choice') and not col[2]['menu_choice']:
                        raise osv.except_osv(_('Error !'),_("You must enter one or more menu choices in column heading"))
                    elif col[2].has_key('menu_choice') and col[2]['menu_choice'].strip() == '':
                        raise osv.except_osv(_('Error !'),_("You must enter one or more menu choices in column heading (white spaces not allowed)"))
        return super(survey_question, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context):
        minimum_ans = 0
        maximum_ans = 0
        if vals.has_key('answer_choice_ids') and  not len(vals['answer_choice_ids']):
            if vals.has_key('type') and vals['type'] not in ['descriptive_text', 'single_textbox', 'comment','table']:
                raise osv.except_osv(_('Error !'),_("You must enter one or more answer."))
        if vals.has_key('column_heading_ids') and  not len(vals['column_heading_ids']):
            if vals.has_key('type') and vals['type'] in ['matrix_of_choices_only_one_ans', 'matrix_of_choices_only_multi_ans', 'matrix_of_drop_down_menus', 'rating_scale']:
                raise osv.except_osv(_('Error !'),_("You must enter one or more column heading."))
        if vals.has_key('required_type') and vals['required_type'] in ['at least', 'at most', 'exactly']:
            if vals['req_ans'] > len(vals['answer_choice_ids']) or not vals['req_ans']:
                raise osv.except_osv(_('Error !'),_("#Required Answer you entered is greater than the number of answer. Please use a number that is smaller than %d.") % (len(vals['answer_choice_ids'])+1))
        if vals.has_key('required_type') and vals['required_type'] == 'a range':
            minimum_ans = vals['minimum_req_ans']
            maximum_ans = vals['maximum_req_ans']
            if vals['minimum_req_ans'] > len(vals['answer_choice_ids']) or not vals['minimum_req_ans']:
                raise osv.except_osv(_('Error !'),_("Minimum Required Answer you entered is greater than the number of answer. Please use a number that is smaller than %d.") % (len(vals['answer_choice_ids'])+1))
            if vals['maximum_req_ans'] > len(vals['answer_choice_ids']) or not vals['maximum_req_ans']:
                raise osv.except_osv(_('Error !'),_("Maximum Required Answer you entered for your maximum is greater than the number of answer. Please use a number that is smaller than %d.") % (len(vals['answer_choice_ids'])+1))
            if maximum_ans <= minimum_ans:
                raise osv.except_osv(_('Error !'),_("Maximum Required Answer is greater than Minimum Required Answer"))
        if vals['type'] ==  'matrix_of_drop_down_menus':
            for col in vals['column_heading_ids']:
                if not col[2]['menu_choice']:
                    raise osv.except_osv(_('Error !'),_("You must enter one or more menu choices in column heading"))
                elif col[2]['menu_choice'].strip() == '':
                    raise osv.except_osv(_('Error !'),_("You must enter one or more menu choices in column heading (white spaces not allowed)"))
        res = super(survey_question, self).create(cr, uid, vals, context)
        return res

    def survey_save(self, cr, uid, ids, context):
        search_obj = self.pool.get('ir.ui.view')
        search_id = search_obj.search(cr,uid,[('model','=','survey.question.wiz'),('name','=','Survey Search')])
        surv_name_wiz = self.pool.get('survey.name.wiz')
        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'transfer':True, 'page_no' : context['page_number'] })
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.question.wiz',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'search_view_id':search_id[0],
                'context': context
                }

    def default_get(self, cr, uid, fields, context={}):
        data = super(survey_question, self).default_get(cr, uid, fields, context)
        if context.has_key('line_order') and context['line_order']:
            if len(context['line_order'][-1]) > 2 and context['line_order'][-1][2].has_key('sequence'):
                data['sequence'] = context['line_order'][-1][2]['sequence'] + 1
        if context.has_key('page_id'):
            data['page_id']= context['page_id']
        return data

survey_question()


class survey_question_column_heading(osv.osv):
    _name = 'survey.question.column.heading'
    _description = 'Survey Question Column Heading'
    _rec_name = 'title'

    def _get_in_visible_rating_weight(self,cr, uid, context={}):
        if context.get('in_visible_rating_weight',False):
            return context['in_visible_rating_weight']
        return False
    def _get_in_visible_menu_choice(self,cr, uid, context={}):
        if context.get('in_visible_menu_choice',False):
            return context['in_visible_menu_choice']
        return False

    _columns = {
        'title' : fields.char('Column Heading', size=128, required=1),
        'menu_choice' : fields.text('Menu Choice'),
        'rating_weight' : fields.integer('Weight'),
        'question_id' : fields.many2one('survey.question', 'Question', ondelete='cascade'),
        'in_visible_rating_weight':fields.boolean('Is Rating Scale Invisible ??'),
        'in_visible_menu_choice':fields.boolean('Is Menu Choice Invisible??')
    }
    _defaults={
       'in_visible_rating_weight':_get_in_visible_rating_weight,
       'in_visible_menu_choice':_get_in_visible_menu_choice,
    }

survey_question_column_heading()

class survey_answer(osv.osv):
    _name = 'survey.answer'
    _description = 'Survey Answer'
    _rec_name = 'answer'
    _order = 'sequence'

    def _calc_response_avg(self, cr, uid, ids, field_name, arg, context):
        val = {}
        for rec in self.browse(cr, uid, ids):
            cr.execute("select count(question_id) ,(select count(answer_id) \
                from survey_response_answer sra, survey_response_line sa \
                where sra.response_id = sa.id and sra.answer_id = %d \
                and sa.state='done') as tot_ans from survey_response_line \
                where question_id = %d and state = 'done'"\
                     % (rec.id, rec.question_id.id))
            res = cr.fetchone()
            if res[0]:
                avg = float(res[1]) * 100 / res[0]
            else:
                avg = 0.0
            val[rec.id] = {
                'response': res[1],
                'average': round(avg, 2),
            }
        return val

    _columns = {
        'question_id' : fields.many2one('survey.question', 'Question', ondelete='cascade'),
        'answer' : fields.char('Answer', size=128, required=1),
        'sequence' : fields.integer('Sequence'),
        'response' : fields.function(_calc_response_avg, method=True, string="#Response", multi='sums'),
        'average' : fields.function(_calc_response_avg, method=True, string="#Avg", multi='sums'),
    }
    _defaults = {
         'sequence' : lambda * a: 1
    }

    def default_get(self, cr, uid, fields, context={}):
        data = super(survey_answer, self).default_get(cr, uid, fields, context)
        if context.has_key('line_order') and context['line_order']:
            if len(context['line_order'][-1]) > 2 and context['line_order'][-1][2].has_key('sequence'):
                data['sequence'] = context['line_order'][-1][2]['sequence'] + 1
        return data

survey_answer()

class survey_response(osv.osv):
    _name = "survey.response"
    _rec_name = 'date_create'
    _columns = {
        'survey_id' : fields.many2one('survey', 'Survey', required=1, ondelete='cascade'),
        'date_create' : fields.datetime('Create Date', required=1),
        'user_id' : fields.many2one('res.users', 'User'),
        'response_type' : fields.selection([('manually', 'Manually'), ('link', 'Link')], 'Response Type', required=1),
        'question_ids' : fields.one2many('survey.response.line', 'response_id', 'Response Answer'),
    }

survey_response()

class survey_response_line(osv.osv):
    _name = 'survey.response.line'
    _description = 'Survey Response Line'
    _rec_name = 'date_create'
    _columns = {
        'response_id' : fields.many2one('survey.response', 'Response', ondelete='cascade'),
        'date_create' : fields.datetime('Create Date', required=1),
        'state' : fields.selection([('draft', 'Draft'), ('done', 'Answered'),('skip', 'Skiped')], 'Status', readonly=True),
        'question_id' : fields.many2one('survey.question', 'Question', ondelete='cascade'),
        'page_id' : fields.related('question_id', 'page_id', type='many2one', relation='survey.page', string='Page'),
        'response_answer_ids' : fields.one2many('survey.response.answer', 'response_id', 'Response Answer'),
        'response_table_ids' : fields.one2many('survey.tbl.column.heading', 'response_table_id', 'Response Answer'),
        'comment' : fields.text('Notes'),
        'single_text' : fields.char('Text', size=255),
    }
    _defaults = {
        'state' : lambda * a: "draft",
    }

    def response_draft(self, cr, uid, ids, arg):
        self.write(cr, uid, ids, { 'state' : 'draft' })
        return True

    def response_done(self, cr, uid, ids, arg):
        self.write(cr, uid, ids, { 'state' : 'done' })
        return True

    def response_skip(self, cr, uid, ids, arg):
        self.write(cr, uid, ids, { 'state' : 'skip' })
        return True

survey_response_line()

class survey_tbl_column_heading(osv.osv):
    _name = 'survey.tbl.column.heading'
    _order = 'name'
    _columns = {
        'name' : fields.integer('Row Number'),
        'column_id' : fields.many2one('survey.question.column.heading', 'Column', ondelete='cascade'),
        'value' : fields.char('Value', size = 255),
        'response_table_id' : fields.many2one('survey.response.line', 'Response', ondelete='cascade'),
    }

survey_tbl_column_heading()

class survey_response_answer(osv.osv):
    _name = 'survey.response.answer'
    _description = 'Survey Response Answer'
    _rec_name = 'response_id'
    _columns = {
        'response_id' : fields.many2one('survey.response.line', 'Response', ondelete='cascade'),
        'answer_id' : fields.many2one('survey.answer', 'Answer', required=1, ondelete='cascade'),
        'answer' : fields.char('Value', size =255),
        'value_choice' : fields.char('Value Choice', size =255),
        'comment' : fields.text('Notes'),
        'comment_field' : fields.char('Comment', size = 255)
    }

survey_response_answer()

class survey_name_wiz(osv.osv_memory):
    _name = 'survey.name.wiz'

    def _get_survey(self, cr, uid, context=None):
        surv_obj = self.pool.get("survey")
        result = []
        if context.has_key('survey_id'):
            for sur in surv_obj.browse(cr, uid, [context['survey_id']]):
                result.append((sur.id, sur.title))
            return result
        group_id = self.pool.get('res.groups').search(cr, uid, [('name', '=', 'Survey / Manager')])
        user_obj = self.pool.get('res.users')
        user_rec = user_obj.read(cr, uid, uid)
        for sur in surv_obj.browse(cr, uid, surv_obj.search(cr, uid, [])):
            if sur.state == 'open':
                if group_id[0]  in user_rec['groups_id']:
                    result.append((sur.id, sur.title))
                elif sur.id in user_rec['survey_id']:
                    result.append((sur.id, sur.title))
        return result

    _columns = {
        'survey_id': fields.selection(_get_survey, "Survey", required="1"),
        'page_no' : fields.integer('Page Number'),
        'note' : fields.text("Description"),
        'page' : fields.char('Page Position',size = 12),
        'transfer' : fields.boolean('Page Transfer'),
        'store_ans' : fields.text('Store Answer'),
        'response' : fields.char('Response',size=16)
    }
    _defaults = {
        'page_no' : lambda * a: - 1,
        'page' : lambda * a: 'next',
        'transfer' : lambda * a: 1,
        'response' : lambda * a: 0,
    }

    def action_next(self, cr, uid, ids, context=None):
        sur_id = self.read(cr, uid, ids, [])[0]
        survey_id = sur_id['survey_id']
        context.update({'survey_id' : survey_id, 'sur_name_id' : sur_id['id']})
        if not context.has_key('active'):
            cr.execute('select count(id) from survey_history where user_id=%s\
                        and survey_id=%s' % (uid,survey_id))
            res = cr.fetchone()[0]
            user_limit = self.pool.get('survey').read(cr, uid, survey_id, ['response_user'])['response_user']
            if user_limit and res >= user_limit:
                raise osv.except_osv(_('Warning !'),_("You can not give response for this survey more than %s times") % (user_limit))
            his_id = self.pool.get('survey.history').create(cr, uid, {'user_id': uid, \
                                              'date': strftime('%Y-%m-%d %H:%M:%S'), 'survey_id': survey_id})
            survey_obj = self.pool.get('survey')
            sur_rec = survey_obj.read(cr,uid,self.read(cr,uid,ids)[0]['survey_id'])
            survey_obj.write(cr, uid, survey_id, {'tot_start_survey' : sur_rec['tot_start_survey'] + 1})
        search_obj = self.pool.get('ir.ui.view')
        search_id = search_obj.search(cr,uid,[('model','=','survey.question.wiz'),('name','=','Survey Search')])
        return {
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'survey.question.wiz',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'search_view_id':search_id[0],
            'context' : context
         }

    def on_change_survey(self, cr, uid, ids, survey_id, context=None):
        notes = self.pool.get('survey').read(cr, uid, survey_id, ['note'])['note']
        return {'value': {'note' : notes}}

survey_name_wiz()

class survey_question_wiz(osv.osv_memory):
    _name = 'survey.question.wiz'
    _columns = {
        'name': fields.integer('Number'),
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False,submenu=False):
        result = super(survey_question_wiz, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar,submenu)
        surv_name_wiz = self.pool.get('survey.name.wiz')
        if view_type in ['form']:
            sur_name_rec = surv_name_wiz.read(cr, uid, context['sur_name_id'])
            survey_id = context['survey_id']
            survey_obj = self.pool.get('survey')
            sur_rec = survey_obj.read(cr, uid, survey_id, [])
            page_obj = self.pool.get('survey.page')
            que_obj = self.pool.get('survey.question')
            ans_obj = self.pool.get('survey.answer')
            response_obj = self.pool.get('survey.response.line')
            que_col_head = self.pool.get('survey.question.column.heading')
            p_id = sur_rec['page_ids']
            total_pages = len(p_id)
            pre_button = False
            if not sur_name_rec['page_no'] + 1 :
                surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'store_ans':{}})
            sur_name_read = surv_name_wiz.read(cr, uid, context['sur_name_id'])
            page_number = int(sur_name_rec['page_no'])
            if sur_name_read['transfer'] or not sur_name_rec['page_no'] + 1:
                surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'transfer':False})
                flag = False
                if sur_name_read['page'] == "next" or sur_name_rec['page_no'] == - 1 :
                    if len(p_id) > sur_name_rec['page_no'] + 1 :
                        if sur_rec['max_response_limit'] and sur_rec['max_response_limit'] <= sur_rec['tot_start_survey'] and not sur_name_rec['page_no'] + 1:
                            survey_obj.write(cr, uid, survey_id, {'state':'close', 'date_close':strftime("%Y-%m-%d %H:%M:%S")})
                        p_id = p_id[sur_name_rec['page_no'] + 1]
                        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'page_no' : sur_name_rec['page_no'] + 1})
                        flag = True
                        page_number += 1
                    if sur_name_rec['page_no'] > - 1:
                        pre_button = True
                else:
                    if sur_name_rec['page_no'] != 0:
                        p_id = p_id[sur_name_rec['page_no'] - 1]
                        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'page_no' : sur_name_rec['page_no'] - 1})
                        flag = True
                        page_number -= 1
                    if sur_name_rec['page_no'] > 1:
                        pre_button = True
                if flag:
                    fields = {}
                    pag_rec = page_obj.read(cr, uid, p_id)
                    xml_form = etree.Element('form', {'string': _(tools.ustr(pag_rec['title']))})
                    etree.SubElement(xml_form, 'label', {'string': to_xml(tools.ustr(pag_rec['note'] or '')), 'align': '0.0', 'colspan':'4'})
                    que_ids = pag_rec['question_ids']
                    qu_no = 0
                    for que in que_ids:
                        qu_no += 1
                        que_rec = que_obj.read(cr, uid, que)
                        descriptive_text = ""
                        separator_string = tools.ustr(qu_no) + "." + tools.ustr(que_rec['question'])
                        if que_rec['is_require_answer'] or que_rec['required_type'] != '':
                            star='*'
                        else:
                            star=''
                        xml_group = etree.SubElement(xml_form, 'group', {'col': '2', 'colspan': '4'})
                        if context.has_key('active') and context.has_key('edit'):
                            xml_group = etree.SubElement(xml_form, 'group', {'col': '1', 'colspan': '2'})
                            etree.SubElement(xml_group, 'separator', {'string': star+to_xml(separator_string), 'colspan': '3'})
                            xml_group1 = etree.SubElement(xml_form, 'group', {'col': '2', 'colspan': '2'})
                            context.update({'question_id' : tools.ustr(que),'page_number' : sur_name_rec['page_no'] , 'transfer' : sur_name_read['transfer'], 'page_id' : p_id})
                            etree.SubElement(xml_group1, 'button', {'string' :'','icon': "gtk-edit", 'type' :'object', 'name':"action_edit_question", 'context' : tools.ustr(context)})
                            etree.SubElement(xml_group1, 'button', {'string' :'','icon': "gtk-delete", 'type' :'object','name':"action_delete_question", 'context' : tools.ustr(context)})
                        else:
                            xml_group = etree.SubElement(xml_form, 'group', {'col': '1', 'colspan': '4'})
                            etree.SubElement(xml_group, 'separator', {'string': star+to_xml(separator_string), 'colspan': '4'})
                        ans_ids = ans_obj.read(cr, uid, que_rec['answer_choice_ids'], [])
                        xml_group = etree.SubElement(xml_form, 'group', {'col': '1', 'colspan': '4'})
                        if que_rec['type'] == 'multiple_choice_only_one_ans':
                            selection = []
                            for ans in ans_ids:
                                selection.append((tools.ustr(ans['id']), ans['answer']))
                            xml_group = etree.SubElement(xml_group, 'group', {'col': '2', 'colspan': '2'})
                            etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_selection"})
                            fields[tools.ustr(que) + "_selection"] = {'type':'selection', 'selection' :selection, 'string':"Answer"}
                        elif que_rec['type'] == 'multiple_choice_multiple_ans':
                            xml_group = etree.SubElement(xml_group, 'group', {'col': '4', 'colspan': '4'})
                            for ans in ans_ids:
                                etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_" + tools.ustr(ans['id'])})
                                fields[tools.ustr(que) + "_" + tools.ustr(ans['id'])] = {'type':'boolean', 'string':ans['answer']}
                        elif que_rec['type'] in ['matrix_of_choices_only_one_ans', 'rating_scale']:
                            if que_rec['comment_column']:
                                col = "4"
                                colspan = "4"
                            else:
                               col = "2"
                               colspan = "2"
                            xml_group = etree.SubElement(xml_group, 'group', {'col': tools.ustr(col), 'colspan': tools.ustr(colspan)})
                            for row in ans_ids:
                                etree.SubElement(xml_group, 'newline')
                                etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_selection_" + tools.ustr(row['id']),'string':to_xml(tools.ustr(row['answer']))})
                                selection = [('','')]
                                for col in que_col_head.read(cr, uid, que_rec['column_heading_ids']):
                                    selection.append((col['title'], col['title']))
                                fields[tools.ustr(que) + "_selection_" + tools.ustr(row['id'])] = {'type':'selection', 'selection' : selection, 'string': "Answer"}
                                if que_rec['comment_column']:
                                   fields[tools.ustr(que) + "_commentcolumn_"+tools.ustr(row['id']) + "_field"] = {'type':'char', 'size' : 255, 'string':tools.ustr(que_rec['column_name']), 'views':{}}
                                   etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_commentcolumn_"+tools.ustr(row['id'])+ "_field"})
                        elif que_rec['type'] == 'matrix_of_choices_only_multi_ans':
                            xml_group = etree.SubElement(xml_group, 'group', {'col': '2', 'colspan': '2'})
                            for row in ans_ids:
                                etree.SubElement(xml_group, 'label', {'string': to_xml(tools.ustr(row['answer'])) +' :-', 'align': '0.0'})
                                etree.SubElement(xml_group, 'newline')
                                for col in que_col_head.read(cr, uid, que_rec['column_heading_ids']):
                                    etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_" + tools.ustr(row['id']) + "_" + tools.ustr(col['title'])})
                                    fields[tools.ustr(que) + "_" + tools.ustr(row['id'])  + "_" + tools.ustr(col['title'])] = {'type':'boolean', 'string': col['title']}
                        elif que_rec['type'] == 'matrix_of_drop_down_menus':
                            xml_group = etree.SubElement(xml_group, 'group', {'col': '2', 'colspan': '2'})
                            for row in ans_ids:
                                etree.SubElement(xml_group, 'label', {'string': to_xml(tools.ustr(row['answer']))+' :-', 'align': '0.0'})
                                etree.SubElement(xml_group, 'newline')
                                for col in que_col_head.read(cr, uid, que_rec['column_heading_ids']):
                                    selection = []
                                    if col['menu_choice']:
                                        for item in col['menu_choice'].split('\n'):
                                            if item and not item.strip() == '': selection.append((item ,item))
                                    etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_" + tools.ustr(row['id']) + "_" + tools.ustr(col['title'])})
                                    fields[tools.ustr(que) + "_" + tools.ustr(row['id'])  + "_" + tools.ustr(col['title'])] = {'type':'selection', 'string': col['title'], 'selection':selection}
                        elif que_rec['type'] == 'multiple_textboxes':
                            xml_group = etree.SubElement(xml_group, 'group', {'col': '1', 'colspan': '4'})
                            for ans in ans_ids:
                                etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_" + tools.ustr(ans['id']) + "_multi"})
                                fields[tools.ustr(que) + "_" + tools.ustr(ans['id']) + "_multi"] = {'type':'char', 'size':255, 'string':ans['answer']}
                        elif que_rec['type'] == 'numerical_textboxes':
                            xml_group = etree.SubElement(xml_group, 'group', {'col': '2', 'colspan': '2'})
                            for ans in ans_ids:
                                etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_" + tools.ustr(ans['id']) + "_numeric"})
                                fields[tools.ustr(que) + "_" + tools.ustr(ans['id']) + "_numeric"] = {'type':'integer', 'string':ans['answer']}
                        elif que_rec['type'] == 'date':
                            xml_group = etree.SubElement(xml_group, 'group', {'col': '2', 'colspan': '2'})
                            for ans in ans_ids:
                                etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_" + tools.ustr(ans['id'])})
                                fields[tools.ustr(que) + "_" + tools.ustr(ans['id'])] = {'type':'date', 'string':ans['answer']}
                        elif que_rec['type'] == 'date_and_time':
                            xml_group = etree.SubElement(xml_group, 'group', {'col': '2', 'colspan': '2'})
                            for ans in ans_ids:
                                etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_" + tools.ustr(ans['id'])})
                                fields[tools.ustr(que) + "_" + tools.ustr(ans['id'])] = {'type':'datetime', 'string':ans['answer']}
                        elif que_rec['type'] == 'descriptive_text':
                            etree.SubElement(xml_group, 'label', {'string': to_xml(tools.ustr(que_rec['descriptive_text']))})
                        elif que_rec['type'] == 'single_textbox':
                            etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_single", 'nolabel':"1" ,'colspan':"4"})
                            fields[tools.ustr(que) + "_single"] = {'type':'char', 'size' : 255, 'string':"single_textbox", 'views':{}}
                        elif que_rec['type'] == 'comment':
                            etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_comment", 'nolabel':"1" ,'colspan':"4"})
                            fields[tools.ustr(que) + "_comment"] = {'type':'text', 'string':"Comment/Eassy Box", 'views':{}}
                        elif que_rec['type'] == 'table':
                            xml_group = etree.SubElement(xml_group, 'group', {'col': str(len(que_rec['column_heading_ids'])), 'colspan': '4'})
                            for col in que_col_head.read(cr, uid, que_rec['column_heading_ids']):
                                etree.SubElement(xml_group, 'separator', {'string': tools.ustr(col['title']),'colspan': '1'})
                            for row in range(0,que_rec['no_of_rows']):
                                for col in que_col_head.read(cr, uid, que_rec['column_heading_ids']):
                                    etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_table_" + tools.ustr(col['id']) +"_"+ tools.ustr(row), 'nolabel':"1"})
                                    fields[tools.ustr(que) + "_table_" + tools.ustr(col['id']) +"_"+ tools.ustr(row)] = {'type':'char','size':255,'views':{}}
                        if que_rec['type'] in ['multiple_choice_only_one_ans', 'multiple_choice_multiple_ans', 'matrix_of_choices_only_one_ans', 'matrix_of_choices_only_multi_ans', 'matrix_of_drop_down_menus', 'rating_scale']:
                            if que_rec['type'] in ['multiple_choice_only_one_ans', 'multiple_choice_multiple_ans'] and que_rec['comment_field_type'] in ['char','text'] and que_rec['make_comment_field']:
                                etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_otherfield", 'colspan':"4"})
                                fields[tools.ustr(que) + "_otherfield"] = {'type':'boolean', 'string':que_rec['comment_label'], 'views':{}}
                                if que_rec['comment_field_type'] == 'char':
                                    etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_other", 'nolabel':"1" ,'colspan':"4"})
                                    fields[tools.ustr(que) + "_other"] = {'type': 'char', 'string': '', 'size':255, 'views':{}}
                                elif que_rec['comment_field_type'] == 'text':
                                    etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_other", 'nolabel':"1" ,'colspan':"4"})
                                    fields[tools.ustr(que) + "_other"] = {'type': 'text', 'string': '', 'views':{}}
                            else:
                                if que_rec['comment_field_type'] == 'char':
                                    etree.SubElement(xml_group, 'label', {'string': to_xml(tools.ustr(que_rec['comment_label'])),'colspan':"4"})
                                    etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_other", 'nolabel':"1" ,'colspan':"4"})
                                    fields[tools.ustr(que) + "_other"] = {'type': 'char', 'string': '', 'size':255, 'views':{}}
                                elif que_rec['comment_field_type'] == 'text':
                                    etree.SubElement(xml_group, 'label', {'string': to_xml(tools.ustr(que_rec['comment_label'])),'colspan':"4"})
                                    etree.SubElement(xml_group, 'field', {'name': tools.ustr(que) + "_other", 'nolabel':"1" ,'colspan':"4"})
                                    fields[tools.ustr(que) + "_other"] = {'type': 'text', 'string': '', 'views':{}}
                    etree.SubElement(xml_form, 'separator', {'colspan': '4'})
                    xml_group = etree.SubElement(xml_form, 'group', {'col': '6', 'colspan': '4'})
                    etree.SubElement(xml_group, 'field', {'name': 'progress_bar_' + tools.ustr(page_number) , 'widget':'progressbar'})
                    fields['progress_bar_' + tools.ustr(page_number)] = {'type':'float', 'string':"Progress", 'views':{}}
                    etree.SubElement(xml_group, 'label', {'string': tools.ustr(page_number+ 1) + "/" + tools.ustr(total_pages)})
                    etree.SubElement(xml_group, 'button', {'icon': "gtk-cancel", 'special': "cancel",'string':"Cancel"})
                    if pre_button:
                        etree.SubElement(xml_group, 'button', {'colspan':"1",'icon':"gtk-go-back",'name':"action_previous",'string':"Previous",'type':"object"})
                    etree.SubElement(xml_group, 'button', {'icon': "gtk-go-forward", 'name':"action_next",'string':"Next",'type':"object"})
                    if context.has_key('active') and context.has_key('edit'):
                        etree.SubElement(xml_form, 'separator', {'string' : '','colspan': '4'})
                        context.update({'page_id' : tools.ustr(p_id),'page_number' : sur_name_rec['page_no'] , 'transfer' : sur_name_read['transfer']})
                        xml_group3 = etree.SubElement(xml_form, 'group', {'col': '4', 'colspan': '4'})
                        etree.SubElement(xml_group3, 'button', {'string' :'Add Page','icon': "gtk-new", 'type' :'object','name':"action_new_page", 'context' : tools.ustr(context)})
                        etree.SubElement(xml_group3, 'button', {'string' :'Edit Page','icon': "gtk-edit", 'type' :'object','name':"action_edit_page", 'context' : tools.ustr(context)})
                        etree.SubElement(xml_group3, 'button', {'string' :'Delete Page','icon': "gtk-delete", 'type' :'object','name':"action_delete_page", 'context' : tools.ustr(context)})
                        etree.SubElement(xml_group3, 'button', {'string' :'Add Question','icon': "gtk-new", 'type' :'object','name':"action_new_question", 'context' : tools.ustr(context)})
                    root = xml_form.getroottree()
                    result['arch'] = etree.tostring(root)
                    result['fields'] = fields
                    result['context'] = context
                else:
                    if not context.has_key('active'):
                        survey_obj.write(cr, uid, survey_id, {'tot_comp_survey' : sur_rec['tot_comp_survey'] + 1})
                    xml_form = etree.Element('form', {'string': _('Complete Survey Response')})
                    etree.SubElement(xml_form, 'separator', {'string': 'Complete Survey', 'colspan': "4"})
                    etree.SubElement(xml_form, 'label', {'string': 'Thanks for your response'})
                    etree.SubElement(xml_form, 'newline')
                    etree.SubElement(xml_form, 'button', {'icon': "gtk-go-forward", 'special':"cancel",'string':"OK",'colspan':"2"})
                    root = xml_form.getroottree()
                    result['arch'] = etree.tostring(root)
                    result['fields'] = {}
                    result['context'] = context
        return result

    def default_get(self, cr, uid, fields_list, context=None):
        value = {}
        for field in fields_list:
            if field.split('_')[0] == 'progress':
                tot_page_id = self.pool.get('survey').browse(cr, uid, context['survey_id'])
                tot_per = (float(100) * (int(field.split('_')[2]) + 1) / len(tot_page_id.page_ids))
                value[field] = tot_per
        if context.has_key('active') and context['active']:
            return value
        surv_name_wiz = self.pool.get('survey.name.wiz')
        sur_name_read = surv_name_wiz.read(cr, uid, context['sur_name_id'])
        ans_list = []
        for key,val in sur_name_read['store_ans'].items():
            for field in fields_list:
                if field in list(val):
                    value[field] = val[field]
        return value

    def create(self, cr, uid, vals, context=None):
        if context.has_key('active') and context['active']:
            return True
        for key,val in vals.items():
            if key.split('_')[0] == "progress":
                vals.pop(key)
                break
        click_state = True
        click_update = []
        surv_name_wiz = self.pool.get('survey.name.wiz')
        surv_all_resp_obj = self.pool.get('survey.response')
        surv_tbl_column_obj = self.pool.get('survey.tbl.column.heading')
        sur_name_read = surv_name_wiz.read(cr, uid, context['sur_name_id'])
        response_id =  0
        if not sur_name_read['response']:
            response_id = surv_all_resp_obj.create(cr, uid, {'response_type':'link', 'user_id':uid, 'date_create':datetime.datetime.now(), 'survey_id' : context['survey_id']})
            surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'response' : tools.ustr(response_id)})
        else:
            response_id = int(sur_name_read['response'])
        for key,val in sur_name_read['store_ans'].items():
            for field in vals:
                if field.split('_')[0] == val['question_id']:
                    click_state = False
                    click_update.append(key)
                    break
        resp_obj = self.pool.get('survey.response.line')
        res_ans_obj = self.pool.get('survey.response.answer')
        que_obj = self.pool.get('survey.question')
        if click_state:
            que_li = []
            resp_id_list = []
            for key, val in vals.items():
                que_id = key.split('_')[0]
                if que_id not in que_li:
                    que_li.append(que_id)
                    que_rec = que_obj.read(cr, uid, [que_id], [])[0]
                    resp_id = resp_obj.create(cr, uid, {'question_id':que_id, 'date_create':datetime.datetime.now(), \
                         'state':'done','response_id' : response_id })
                    resp_id_list.append(resp_id)
                    sur_name_read['store_ans'].update({resp_id:{'question_id':que_id}})
                    surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'store_ans':sur_name_read['store_ans']})
                    select_count = 0
                    numeric_sum = 0
                    selected_value = []
                    matrix_list = []
                    comment_field = False
                    comment_value = False
                    response_list = []
                    for key1, val1 in vals.items():
                        if val1 and key1.split('_')[1] == "table" and key1.split('_')[0] == que_id:
                            surv_tbl_column_obj.create(cr, uid, {'response_table_id' : resp_id,'column_id':key1.split('_')[2], 'name':key1.split('_')[3], 'value' : val1})
                            sur_name_read['store_ans'][resp_id].update({key1:val1})
                            select_count += 1
                        elif val1 and key1.split('_')[1] == "otherfield" and key1.split('_')[0] == que_id:
                            comment_field = True
                            sur_name_read['store_ans'][resp_id].update({key1:val1})
                            select_count += 1
                            surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'store_ans':sur_name_read['store_ans']})
                            continue
                        elif val1 and key1.split('_')[1] == "selection" and key1.split('_')[0] == que_id:
                            if len(key1.split('_')) > 2:
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':resp_id, 'answer_id':key1.split('_')[-1], 'answer' : val1})
                                selected_value.append(val1)
                                response_list.append(str(ans_create_id) + "_" + str(key1.split('_')[-1]))
                            else:
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':resp_id, 'answer_id':val1})
                            sur_name_read['store_ans'][resp_id].update({key1:val1})
                            select_count += 1
                        elif key1.split('_')[1] == "other" and key1.split('_')[0] == que_id:
                            if not val1:
                                comment_value = True
                            else:
                                error = False
                                if que_rec['comment_valid_type'] == 'must_be_specific_length':
                                    if (not val1 and  que_rec['validation_minimum_no']) or len(val1) <  que_rec['validation_maximum_no'] or len(val1) > que_rec['comment_maximum_no']:
                                        error = True
                                elif que_rec['comment_valid_type'] in ['must_be_whole_number', 'must_be_decimal_number', 'must_be_date']:
                                    error = False
                                    try:
                                        if que_rec['comment_valid_type'] == 'must_be_whole_number':
                                            value = int(val1)
                                            if value <  que_rec['validation_minimum_no'] or value > que_rec['validation_maximum_no']:
                                                error = True
                                        elif que_rec['comment_valid_type'] == 'must_be_decimal_number':
                                            value = float(val1)
                                            if value <  que_rec['comment_minimum_float'] or value > que_rec['comment_maximum_float']:
                                                error = True
                                        elif que_rec['comment_valid_type'] == 'must_be_date':
                                            value = datetime.datetime.strptime(val1, "%Y-%m-%d")
                                            if value <  datetime.datetime.strptime(que_rec['comment_minimum_date'], "%Y-%m-%d") or value >  datetime.datetime.strptime(que_rec['comment_maximum_date'], "%Y-%m-%d"):
                                                error = True
                                    except:
                                        error = True
                                elif que_rec['comment_valid_type'] == 'must_be_email_address':
                                    import re
                                    if re.match("^[a-zA-Z0-9._%-+]+@[a-zA-Z0-9._%-]+.[a-zA-Z]{2,6}$", val1) == None:
                                            error = True
                                if error:
                                    for res in resp_id_list:
                                        sur_name_read['store_ans'].pop(res)
                                    surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'response' :0})
                                    raise osv.except_osv(_('Error !'), _("'" + que_rec['question'] + "'  \n" + tools.ustr(que_rec['comment_valid_err_msg'])))
                                resp_obj.write(cr, uid, resp_id, {'comment':val1})
                                sur_name_read['store_ans'][resp_id].update({key1:val1})
                        elif val1 and key1.split('_')[1] == "comment" and key1.split('_')[0] == que_id:
                            resp_obj.write(cr, uid, resp_id, {'comment':val1})
                            sur_name_read['store_ans'][resp_id].update({key1:val1})
                            select_count += 1
                        elif val1 and key1.split('_')[0] == que_id and (key1.split('_')[1] == "single"  or (len(key1.split('_')) > 2 and key1.split('_')[2] == 'multi')):
                            error = False
                            if que_rec['validation_type'] == 'must_be_specific_length':
                                if (not val1 and  que_rec['validation_minimum_no']) or len(val1) <  que_rec['validation_minimum_no'] or len(val1) > que_rec['validation_maximum_no']:
                                    error = True
                            elif que_rec['validation_type'] in ['must_be_whole_number', 'must_be_decimal_number', 'must_be_date']:
                                error = False
                                try:
                                    if que_rec['validation_type'] == 'must_be_whole_number':
                                        value = int(val1)
                                        if value <  que_rec['validation_minimum_no'] or value > que_rec['validation_maximum_no']:
                                            error = True
                                    elif que_rec['validation_type'] == 'must_be_decimal_number':
                                        value = float(val1)
                                        if value <  que_rec['validation_minimum_float'] or value > que_rec['validation_maximum_float']:
                                            error = True
                                    elif que_rec['validation_type'] == 'must_be_date':
                                        value = datetime.datetime.strptime(val1, "%Y-%m-%d")
                                        if value <  datetime.datetime.strptime(que_rec['validation_minimum_date'], "%Y-%m-%d") or value >  datetime.datetime.strptime(que_rec['validation_maximum_date'], "%Y-%m-%d"):
                                            error = True
                                except:
                                    error = True
                            elif que_rec['validation_type'] == 'must_be_email_address':
                                import re
                                if re.match("^[a-zA-Z0-9._%-+]+@[a-zA-Z0-9._%-]+.[a-zA-Z]{2,6}$", val1) == None:
                                        error = True
                            if error:
                                for res in resp_id_list:
                                    sur_name_read['store_ans'].pop(res)
                                surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'response' :0})
                                raise osv.except_osv(_('Error !'), _("'" + que_rec['question'] + "'  \n" + tools.ustr(que_rec['validation_valid_err_msg'])))
                            if key1.split('_')[1] == "single" :
                                resp_obj.write(cr, uid, resp_id, {'single_text':val1})
                            else:
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':resp_id, 'answer_id':key1.split('_')[1], 'answer' : val1})
                            sur_name_read['store_ans'][resp_id].update({key1:val1})
                            select_count += 1
                        elif val1 and que_id == key1.split('_')[0] and len(key1.split('_')) > 2 and key1.split('_')[2] == 'numeric':
                            ans_create_id = res_ans_obj.create(cr, uid, {'response_id':resp_id, 'answer_id':key1.split('_')[1], 'answer' : val1})
                            sur_name_read['store_ans'][resp_id].update({key1:val1})
                            select_count += 1
                            numeric_sum += int(val1)
                        elif val1 and que_id == key1.split('_')[0] and len(key1.split('_')) == 3:
                            if type(val1) == type('') or type(val1) == type(u''):
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':resp_id, 'answer_id':key1.split('_')[1], 'answer' : key1.split('_')[2], 'value_choice' : val1})
                                sur_name_read['store_ans'][resp_id].update({key1:val1})
                            else:
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':resp_id, 'answer_id':key1.split('_')[1], 'answer' : key1.split('_')[2]})
                                sur_name_read['store_ans'][resp_id].update({key1:True})
                            matrix_list.append(key1.split('_')[0] + '_' + key1.split('_')[1])
                            select_count += 1
                        elif val1 and que_id == key1.split('_')[0] and len(key1.split('_')) == 2:
                            ans_create_id = res_ans_obj.create(cr, uid, {'response_id':resp_id, 'answer_id':key1.split('_')[-1], 'answer' : val1})
                            sur_name_read['store_ans'][resp_id].update({key1:val1})
                            select_count += 1
                        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'store_ans':sur_name_read['store_ans']})
                    for key,val in vals.items():
                        if val and key.split('_')[1] == "commentcolumn" and key.split('_')[0] == que_id:
                            for res_id in response_list:
                                if key.split('_')[2] in res_id.split('_')[1]:
                                    a = res_ans_obj.write(cr, uid, [res_id.split('_')[0]], {'comment_field':val})
                                    sur_name_read['store_ans'][resp_id].update({key:val})
                    if comment_field and comment_value:
                        for res in resp_id_list:
                            sur_name_read['store_ans'].pop(res)
                        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'response' :0})
                        raise osv.except_osv(_('Error re !'), _("'" + que_rec['question']  + "' " + tools.ustr(que_rec['make_comment_field_err_msg'])))
                    if que_rec['type'] == "rating_scale" and que_rec['rating_allow_one_column_require'] and len(selected_value) > len(list(set(selected_value))):
                        for res in resp_id_list:
                            sur_name_read['store_ans'].pop(res)
                        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'response' :0})
                        raise osv.except_osv(_('Error re !'), _("'" + que_rec['question'] + "\n you cannot select same answer more than one times'"))
                    if not select_count:
                        resp_obj.write(cr, uid, resp_id, {'state':'skip'})
                    if que_rec['numeric_required_sum'] and numeric_sum > que_rec['numeric_required_sum']:
                        for res in resp_id_list:
                            sur_name_read['store_ans'].pop(res)
                        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'response' :0})
                        raise osv.except_osv(_('Error re !'), _("'" + que_rec['question'] + "' " + tools.ustr(que_rec['numeric_required_sum_err_msg'])))
                    if que_rec['type'] in ['multiple_choice_multiple_ans','matrix_of_choices_only_one_ans','matrix_of_choices_only_multi_ans','matrix_of_drop_down_menus','rating_scale','multiple_textboxes','numerical_textboxes','date','date_and_time'] and que_rec['required_type']:
                        if matrix_list:
                            if (que_rec['required_type'] == 'all' and len(list(set(matrix_list))) < len(que_rec['answer_choice_ids'])) or \
                            (que_rec['required_type'] == 'at least' and len(list(set(matrix_list))) < que_rec['req_ans']) or \
                            (que_rec['required_type'] == 'at most' and len(list(set(matrix_list))) > que_rec['req_ans']) or \
                            (que_rec['required_type'] == 'exactly' and len(list(set(matrix_list))) != que_rec['req_ans']) or \
                            (que_rec['required_type'] == 'a range' and (len(list(set(matrix_list))) < que_rec['minimum_req_ans'] or len(list(set(matrix_list))) > que_rec['maximum_req_ans'])):
                                for res in resp_id_list:
                                    sur_name_read['store_ans'].pop(res)
                                surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'response' :0})
                                raise osv.except_osv(_('Error !'), _("'" + que_rec['question'] + "' " + tools.ustr(que_rec['req_error_msg'])))
                        elif (que_rec['required_type'] == 'all' and select_count < len(que_rec['answer_choice_ids'])) or \
                            (que_rec['required_type'] == 'at least' and select_count < que_rec['req_ans']) or \
                            (que_rec['required_type'] == 'at most' and select_count > que_rec['req_ans']) or \
                            (que_rec['required_type'] == 'exactly' and select_count != que_rec['req_ans']) or \
                            (que_rec['required_type'] == 'a range' and (select_count < que_rec['minimum_req_ans'] or select_count > que_rec['maximum_req_ans'])):
                            for res in resp_id_list:
                                sur_name_read['store_ans'].pop(res)
                            surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'response' :0})
                            raise osv.except_osv(_('Error !'), _("'" + que_rec['question'] + "' " + tools.ustr(que_rec['req_error_msg'])))
                    if que_rec['type'] in ['multiple_choice_only_one_ans','single_textbox','comment'] and  que_rec['is_require_answer'] and select_count <= 0:
                        for res in resp_id_list:
                            sur_name_read['store_ans'].pop(res)
                        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'response' :0})
                        raise osv.except_osv(_('Error re !'), _("'" + que_rec['question'] + "' " + tools.ustr(que_rec['req_error_msg'])))
        else:
            resp_id_list = []
            for update in click_update:
                que_rec = que_obj.read(cr, uid , [sur_name_read['store_ans'][update]['question_id']], [])[0]
                res_ans_obj.unlink(cr, uid,res_ans_obj.search(cr, uid, [('response_id', '=', update)]))
                surv_tbl_column_obj.unlink(cr, uid,surv_tbl_column_obj.search(cr, uid, [('response_table_id', '=', update)]))
                resp_id_list.append(update)
                sur_name_read['store_ans'].update({update:{'question_id':sur_name_read['store_ans'][update]['question_id']}})
                surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'store_ans':sur_name_read['store_ans']})
                select_count = 0
                numeric_sum = 0
                selected_value = []
                matrix_list = []
                comment_field = False
                comment_value = False
                response_list = []
                for key, val in vals.items():
                    ans_id_len = key.split('_')
                    if ans_id_len[0] == sur_name_read['store_ans'][update]['question_id']:
                        if val and key.split('_')[1] == "table":
                            surv_tbl_column_obj.create(cr, uid, {'response_table_id' : update,'column_id':key.split('_')[2], 'name':key.split('_')[3], 'value' : val})
                            sur_name_read['store_ans'][update].update({key:val})
                            resp_obj.write(cr, uid, update, {'state': 'done'})
                        elif val and key.split('_')[1] == "otherfield" :
                            comment_field = True
                            sur_name_read['store_ans'][update].update({key:val})
                            select_count += 1
                            surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'store_ans':sur_name_read['store_ans']})
                            continue
                        elif val and key.split('_')[1] == "selection":
                            if len(key.split('_')) > 2:
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':update, 'answer_id':key.split('_')[-1], 'answer' : val})
                                selected_value.append(val)
                                response_list.append(str(ans_create_id) + "_" + str(key.split('_')[-1]))
                            else:
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':update, 'answer_id': val})
                            resp_obj.write(cr, uid, update, {'state': 'done'})
                            sur_name_read['store_ans'][update].update({key:val})
                            select_count += 1
                        elif key.split('_')[1] == "other":
                            if not val:
                                comment_value = True
                            else:
                                error = False
                                if que_rec['comment_valid_type'] == 'must_be_specific_length':
                                    if (not val and  que_rec['comment_minimum_no']) or len(val) <  que_rec['comment_minimum_no'] or len(val) > que_rec['comment_maximum_no']:
                                        error = True
                                elif que_rec['comment_valid_type'] in ['must_be_whole_number', 'must_be_decimal_number', 'must_be_date']:
                                    try:
                                        if que_rec['comment_valid_type'] == 'must_be_whole_number':
                                            value = int(val)
                                            if value <  que_rec['comment_minimum_no'] or value > que_rec['comment_maximum_no']:
                                                error = True
                                        elif que_rec['comment_valid_type'] == 'must_be_decimal_number':
                                            value = float(val)
                                            if value <  que_rec['comment_minimum_float'] or value > que_rec['comment_maximum_float']:
                                                error = True
                                        elif que_rec['comment_valid_type'] == 'must_be_date':
                                            value = datetime.datetime.strptime(val, "%Y-%m-%d")
                                            if value <  datetime.datetime.strptime(que_rec['comment_minimum_date'], "%Y-%m-%d") or value >  datetime.datetime.strptime(que_rec['comment_maximum_date'], "%Y-%m-%d"):
                                                error = True
                                    except:
                                        error = True
                                elif que_rec['comment_valid_type'] == 'must_be_email_address':
                                    import re
                                    if re.match("^[a-zA-Z0-9._%-+]+@[a-zA-Z0-9._%-]+.[a-zA-Z]{2,6}$", val) == None:
                                            error = True
                                if error:
                                    raise osv.except_osv(_('Error !'), _("'" + que_rec['question'] + "'  \n" + tools.ustr(que_rec['comment_valid_err_msg'])))
                                resp_obj.write(cr, uid, update, {'comment':val,'state': 'done'})
                                sur_name_read['store_ans'][update].update({key:val})
                        elif val and key.split('_')[1] == "comment":
                            resp_obj.write(cr, uid, update, {'comment':val,'state': 'done'})
                            sur_name_read['store_ans'][update].update({key:val})
                            select_count += 1
                        elif val and (key.split('_')[1] == "single"  or (len(key.split('_')) > 2 and key.split('_')[2] == 'multi')):
                            error = False
                            if que_rec['validation_type'] == 'must_be_specific_length':
                                if (not val and  que_rec['validation_minimum_no']) or len(val) <  que_rec['validation_minimum_no'] or len(val) > que_rec['validation_maximum_no']:
                                    error = True
                            elif que_rec['validation_type'] in ['must_be_whole_number', 'must_be_decimal_number', 'must_be_date']:
                                error = False
                                try:
                                    if que_rec['validation_type'] == 'must_be_whole_number':
                                        value = int(val)
                                        if value <  que_rec['validation_minimum_no'] or value > que_rec['validation_maximum_no']:
                                            error = True
                                    elif que_rec['validation_type'] == 'must_be_decimal_number':
                                        value = float(val)
                                        if value <  que_rec['validation_minimum_float'] or value > que_rec['validation_maximum_float']:
                                            error = True
                                    elif que_rec['validation_type'] == 'must_be_date':
                                        value = datetime.datetime.strptime(val, "%Y-%m-%d")
                                        if value <  datetime.datetime.strptime(que_rec['validation_minimum_date'], "%Y-%m-%d") or value >  datetime.datetime.strptime(que_rec['validation_maximum_date'], "%Y-%m-%d"):
                                            error = True
                                except Exception ,e:
                                    error = True
                            elif que_rec['validation_type'] == 'must_be_email_address':
                                import re
                                if re.match("^[a-zA-Z0-9._%-+]+@[a-zA-Z0-9._%-]+.[a-zA-Z]{2,6}$", val) == None:
                                        error = True
                            if error:
                                raise osv.except_osv(_('Error !'), _("'" + que_rec['question'] + "'  \n" + tools.ustr(que_rec['validation_valid_err_msg'])))
                            if key.split('_')[1] == "single" :
                                resp_obj.write(cr, uid, update, {'single_text':val,'state': 'done'})
                            else:
                                resp_obj.write(cr, uid, update, {'state': 'done'})
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':update, 'answer_id':ans_id_len[1], 'answer' : val})
                            sur_name_read['store_ans'][update].update({key:val})
                            select_count += 1
                        elif val and len(key.split('_')) > 2 and key.split('_')[2] == 'numeric':
                            resp_obj.write(cr, uid, update, {'state': 'done'})
                            ans_create_id = res_ans_obj.create(cr, uid, {'response_id':update, 'answer_id':ans_id_len[1], 'answer' : val})
                            sur_name_read['store_ans'][update].update({key:val})
                            select_count += 1
                            numeric_sum += int(val)
                        elif val and len(key.split('_')) == 3:
                            resp_obj.write(cr, uid, update, {'state': 'done'})
                            if type(val) == type(''):
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':update, 'answer_id':ans_id_len[1], 'answer' : ans_id_len[2], 'value_choice' : val})
                                sur_name_read['store_ans'][update].update({key:val})
                            else:
                                ans_create_id = res_ans_obj.create(cr, uid, {'response_id':update, 'answer_id':ans_id_len[1], 'answer' : ans_id_len[2]})
                                sur_name_read['store_ans'][update].update({key:True})
                            matrix_list.append(key.split('_')[0] + '_' + key.split('_')[1])
                            select_count += 1
                        elif val and len(key.split('_')) == 2:
                            resp_obj.write(cr, uid, update, {'state': 'done'})
                            ans_create_id = res_ans_obj.create(cr, uid, {'response_id':update, 'answer_id':ans_id_len[-1], 'answer' : val})
                            sur_name_read['store_ans'][update].update({key:val})
                            select_count += 1
                        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'store_ans':sur_name_read['store_ans']})
                for key,val in vals.items():
                    if val and key.split('_')[1] == "commentcolumn" and key.split('_')[0] == sur_name_read['store_ans'][update]['question_id']:
                        for res_id in response_list:
                            if key.split('_')[2] in res_id.split('_')[1]:
                                a = res_ans_obj.write(cr, uid, [res_id.split('_')[0]], {'comment_field':val})
                                sur_name_read['store_ans'][update].update({key:val})
                if comment_field and comment_value:
                    raise osv.except_osv(_('Error re !'), _("'" + que_rec['question']  + "' " + tools.ustr(que_rec['make_comment_field_err_msg'])))
                if que_rec['type'] == "rating_scale" and que_rec['rating_allow_one_column_require'] and len(selected_value) > len(list(set(selected_value))):
                    raise osv.except_osv(_('Error re !'), _("'" + que_rec['question'] + "\n you cannot select same answer more than one times'"))
                if que_rec['numeric_required_sum'] and numeric_sum > que_rec['numeric_required_sum']:
                    raise osv.except_osv(_('Error re !'), _("'" + que_rec['question'] + "' " + tools.ustr(que_rec['numeric_required_sum_err_msg'])))
                if not select_count:
                    resp_obj.write(cr, uid, update, {'state': 'skip'})
                if que_rec['type'] in ['multiple_choice_multiple_ans','matrix_of_choices_only_one_ans','matrix_of_choices_only_multi_ans','matrix_of_drop_down_menus','rating_scale','multiple_textboxes','numerical_textboxes','date','date_and_time'] and que_rec['required_type']:
                    if matrix_list:
                        if (que_rec['required_type'] == 'all' and len(list(set(matrix_list))) < len(que_rec['answer_choice_ids'])) or \
                        (que_rec['required_type'] == 'at least' and len(list(set(matrix_list))) < que_rec['req_ans']) or \
                        (que_rec['required_type'] == 'at most' and len(list(set(matrix_list))) > que_rec['req_ans']) or \
                        (que_rec['required_type'] == 'exactly' and len(list(set(matrix_list))) != que_rec['req_ans']) or \
                        (que_rec['required_type'] == 'a range' and (len(list(set(matrix_list))) < que_rec['minimum_req_ans'] or len(list(set(matrix_list))) > que_rec['maximum_req_ans'])):
                            raise osv.except_osv(_('Error !'), _("'" + que_rec['question'] + "' " + tools.ustr(que_rec['req_error_msg'])))
                    elif (que_rec['required_type'] == 'all' and select_count < len(que_rec['answer_choice_ids'])) or \
                        (que_rec['required_type'] == 'at least' and select_count < que_rec['req_ans']) or \
                        (que_rec['required_type'] == 'at most' and select_count > que_rec['req_ans']) or \
                        (que_rec['required_type'] == 'exactly' and select_count != que_rec['req_ans']) or \
                        (que_rec['required_type'] == 'a range' and (select_count < que_rec['minimum_req_ans'] or select_count > que_rec['maximum_req_ans'])):
                            raise osv.except_osv(_('Error !'), _("'" + que_rec['question'] + "' " + tools.ustr(que_rec['req_error_msg'])))
                if que_rec['type'] in ['multiple_choice_only_one_ans','single_textbox','comment'] and  que_rec['is_require_answer'] and select_count <= 0:
                    raise osv.except_osv(_('Error re !'), _("'" + que_rec['question'] + "' " + tools.ustr(que_rec['req_error_msg'])))
        return True

    def action_new_question(self,cr, uid, ids, context):
        for key,val in context.items():
            if type(key) == type(True):
                context.pop(key)
        view_id = self.pool.get('ir.ui.view').search(cr,uid,[('model','=','survey.question'),('name','=','survey_question_wizard_test')])
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.question',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'view_id': view_id,
                'context': context
                }

    def action_new_page(self, cr, uid, ids, context):
        for key,val in context.items():
            if type(key) == type(True):
                context.pop(key)
        view_id = self.pool.get('ir.ui.view').search(cr,uid,[('model','=','survey.page'),('name','=','survey_page_wizard_test')])
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.page',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'view_id': view_id,
                'context': context
                }

    def action_edit_page(self,cr, uid, ids, context):
        for key,val in context.items():
            if type(key) == type(True):
                context.pop(key)
        view_id = self.pool.get('ir.ui.view').search(cr,uid,[('model','=','survey.page'),('name','=','survey_page_wizard_test')])
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.page',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'res_id' : int(context['page_id']),
                'view_id': view_id,
                'context': context
                }

    def action_delete_page(self,cr, uid, ids, context):
        for key,val in context.items():
            if type(key) == type(True):
                context.pop(key)
        self.pool.get('survey.page').unlink(cr, uid, [context['page_id']])
        search_id = self.pool.get('ir.ui.view').search(cr,uid,[('model','=','survey.question.wiz'),('name','=','Survey Search')])
        surv_name_wiz = self.pool.get('survey.name.wiz')
        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'transfer':True, 'page_no' : context['page_number'] })
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.question.wiz',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'search_view_id':search_id[0],
                'context': context
                }

    def action_edit_question(self,cr, uid, ids, context):
        for key,val in context.items():
            if type(key) == type(True):
                context.pop(key)
        view_id = self.pool.get('ir.ui.view').search(cr,uid,[('model','=','survey.question'),('name','=','survey_question_wizard_test')])
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.question',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'res_id' : int(context['question_id']),
                'view_id': view_id,
                'context': context
                }

    def action_delete_question(self,cr, uid, ids, context):
        for key,val in context.items():
            if type(key) == type(True):
                context.pop(key)
        que_obj = self.pool.get('survey.question')
        que_obj.unlink(cr, uid, [context['question_id']])
        search_id = self.pool.get('ir.ui.view').search(cr,uid,[('model','=','survey.question.wiz'),('name','=','Survey Search')])
        surv_name_wiz = self.pool.get('survey.name.wiz')
        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'transfer':True, 'page_no' : context['page_number'] })
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.question.wiz',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'search_view_id':search_id[0],
                'context': context
                }

    def action_next(self, cr, uid, ids, context=None):
        surv_name_wiz = self.pool.get('survey.name.wiz')
        search_obj = self.pool.get('ir.ui.view')
        search_id = search_obj.search(cr,uid,[('model','=','survey.question.wiz'),('name','=','Survey Search')])
        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'transfer':True, 'page':'next'})
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.question.wiz',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'search_view_id':search_id[0],
                'context': context
                }

    def action_previous(self, cr, uid, ids, context=None):
        surv_name_wiz = self.pool.get('survey.name.wiz')
        search_obj = self.pool.get('ir.ui.view')
        search_id = search_obj.search(cr,uid,[('model','=','survey.question.wiz'),('name','=','Survey Search')])
        surv_name_wiz.write(cr, uid, [context['sur_name_id']], {'transfer':True, 'page':'previous'})
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'survey.question.wiz',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'search_view_id':search_id[0],
                'context': context
                }

survey_question_wiz()

class res_users(osv.osv):
    _inherit = "res.users"
    _name = "res.users"
    _columns = {
        'survey_id': fields.many2many('survey', 'survey_users_rel', 'uid', 'sid', 'Groups'),
    }

res_users()

class survey_request(osv.osv):
    _name = "survey.request"
    _order = 'date_deadline'
    _columns = {
        'date_deadline' : fields.date("Deadline date"),
        'user_id' : fields.many2one("res.users", "User"),
        'email' : fields.char("E-mail", size=64),
        'survey_id' : fields.many2one("survey", "Survey", required=1),
        'answer_ids' : fields.one2many('survey.answer', 'question_id', 'Answer'),
        'state' : fields.selection([('waitin_answer', 'Wating Answer'),('done', 'Done'),('cancelled', 'Cancelled')], 'State')
    }

survey_request()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
