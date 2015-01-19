{
    'name': "Lead Scoring",
    'category': "CRM",
    'version': "1.0",
    'depends': ['base', 'sales_team', 'marketing', 'website_crm'],
    'author': "Odoo S.A.",
    'description': """\
    Lead scoring""",
    'data': [
        'views/website_crm_score.xml',
        'views/reporting.xml',
        'views/sales.xml',
        'views/marketing.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'demo/website_crm_score_demo.xml',
    ],
    'installable': True,
}
