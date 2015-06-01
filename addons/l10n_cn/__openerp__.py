# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (C) 2008-2008 凯源吕鑫 lvxin@gmail.com   <basic chart data>
#                         维智众源 oldrev@gmail.com  <states data>
# Copyright (C) 2012-2012 南京盈通 ccdos@intoerp.com <small business chart>
# Copyright (C) 2008-now  开阖软件 jeff@osbzr.com    < PM and LTS >

{
    'name': '中国会计科目表',
    'version': '1.8',
    'category': 'Localization/Account Charts',
    'author': 'www.openerp-china.org',
    'maintainer':'jeff@osbzr.com',
    'website':'http://openerp-china.org',
    'description': """

    科目类型\会计科目表模板\增值税\辅助核算类别\管理会计凭证簿\财务会计凭证簿

    添加中文省份数据

    增加小企业会计科目表
    
    """,
    'depends': ['base','account'],
    'demo': [],
    'data': [
        'account_chart_type.xml',
        'account_chart_template.xml',
        'account_chart_small_business_template.xml',
        'l10n_chart_cn_wizard.xml',
        'base_data.xml',
    ],
    'auto_install': False,
    'installable': False,
}
