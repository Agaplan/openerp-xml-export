#!/usr/bin/env python

#
# XML Export, (C) Agaplan 2011
#

{
    'name': 'XML Export',
    'version': '1.0',
    'description': """Allows exporting any model via a defined XML model""",
    'category': 'Generic Modules/Export',
    'author': 'Agaplan',
    'website': 'http://www.agaplan.eu',
    'depends': [
        'base',
    ],
    'init_xml': [],
    'update_xml': [
        'wizard/xml_export_wizard_view.xml',
        'views/xml_export_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo_xml': [],
    'test': [],
    'installable': True,
}

# vim:sts=4:et
