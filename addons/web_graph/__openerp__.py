{
    "name": "web Graph",
    "category" : "Hidden",
    "description":'Openerp web graph view',
    "version": "2.0",
    "depends": ['web'],
    "js": [
           "static/lib/dhtmlxGraph/codebase/dhtmlxchart.js",
           "static/src/js/graph.js"],
    "css": ["static/lib/dhtmlxGraph/codebase/dhtmlxchart.css"],
    'qweb' : [
        "static/src/xml/*.xml",
    ],
    "active": True
}
