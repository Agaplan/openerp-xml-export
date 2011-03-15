#!/usr/bin/env python

#
# XML Export, (C) Agaplan 2011

from osv import osv,fields
from tools.translate import _

class xml_export(osv.osv):
    _name = "xml.export"
    _description = "XML Export Definition"

    _columns = {
        'name': fields.char('Export Name', size=64, required=True),
        'state': fields.selection( ( ('draft','Draft'), ('used','In Use'), ('deprecated', 'Deprecated') ), string='State', required=True, readonly=True),
        'field_ids': fields.one2many('xml.export.field', 'export_id', 'Fields'),
        'head_xml': fields.text('Header'),
        'feet_xml': fields.text('Footer'),
        'validation_type': fields.selection( ( ('none', 'None'), ('xsd', 'XSD Schema'), ('rng', 'RelaxNG Schema'), ('schematron', 'SchemaTron') ), 'Validation type'),
        'validation_file': fields.binary('Validation file'),
        'namespace': fields.char('Namespace', size=64),
        'schema': fields.char('Schema', size=64),
        'root': fields.char('Root', size=64, required=True),
    }

    _defaults = {
        'state': 'draft',
    }
xml_export()

class xml_export_field(osv.osv):
    _name = "xml.export.field"
    _description = "XML Field"
    _order = "sequence, id"

    def _get_xml_path(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for field in self.read(cr, uid, ids, ['id','parent_id','name','export_id'], context):
            xml_path = ""

            if not field['parent_id']:
                root = self.pool.get('xml.export').read(cr, uid, field['export_id'][0], ['root'])['root']
                xml_path = "/" + root
            else:
                parent_id = field['parent_id'][0]
                parent_path = self._get_xml_path(cr, uid, [parent_id], ['xml_path'], None, context=context)[parent_id]
                xml_path = parent_path or ''

            # Finally add ourself
            xml_path += '/' + field['name']
            res[ field['id'] ] = xml_path
        return res

    def _get_child_fields(self, cr, uid, ids, context=None):
        """
            Return list of children which need to update their xml_path values
        """
        res = self.search(cr, uid, [('parent_id','child_of',ids)], context=context)
        return res

    def _get_fields_from_root(self, cr, uid, ids, context=None):
        """
            ids will be an id of xml.export, we need to return list of ids related to this export
        """
        res = self.pool.get('xml.export.field').search(cr, uid, [('export_id','in',ids)], context=context)
        return res

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int,long)):
            ids = [ids]
        res = self.read(cr, uid, ids, ['xml_path'], context=context)
        res = [(x['id'], x['xml_path']) for x in res]
        return res

    _columns = {
        'export_id': fields.many2one('xml.export', 'XML Export', required=True, ondelete="cascade"),
        'name': fields.char('Name',size=64, required=True),
        'parent_id': fields.many2one('xml.export.field', 'Child of', ondelete="restrict"),
        'sequence': fields.integer('Sequence'),
        'child_ids': fields.one2many('xml.export.field', 'parent_id', 'Child fields'),
        'min_qty': fields.integer('Minimal entries'),
        'max_qty': fields.integer('Maximum entries', help='Use -1 for unlimited'),
        'type': fields.selection(
            (
                ('text','Text'),
                ('decimal','Decimal'),
                ('choice','Choice'),
                ('empty','Empty'),
            ), string='Type', required=True),
        'length': fields.integer('Field length'),
        'description': fields.text('Description', translate=True),
        'xml_path': fields.function(fnct=_get_xml_path, method=True, type="char", size=256, string="XML Path",
            store={
                'xml.export.field': (_get_child_fields, ['name', 'parent_id'], 10),
                'xml.export': (_get_fields_from_root, ['root'], 20),
            }
        ),
    }
xml_export_field()

class xml_profile(osv.osv):
    _name = "xml.profile"
    _description = "XML Profile"

    _columns = {
        'name': fields.char('Name',size=64,translate=True),
        'export_id': fields.many2one('xml.export', 'XML Definition', required=True, ondelete="restrict"),
        'lines': fields.one2many('xml.profile.line', 'profile_id', 'Lines'),
        'description': fields.text('Description'),
    }

    def action_fill(self, cr, uid, ids, context=None):
        me = self.browse(cr, uid, ids[0], context)
        if not me.export_id:
            raise osv.osv_except(_("XML Definition missing"), _("You need to select an export schema first !"))

        res_id = []
        pl_obj = self.pool.get('xml.profile.line')
        for field in me.export_id.field_ids:
            line_id = pl_obj.create(cr, uid, {
                'profile_id': me.id,
                'action': 'compute',
                'xml_field': field.id,
            }, context=context)
            res_id.append(line_id)
        return True

xml_profile()

class xml_profile_line(osv.osv):
    _name = "xml.profile.line"
    _description = "XML Profile line"

    _columns = {
        'profile_id': fields.many2one('xml.profile', 'XML Profile', required=True),
        'xml_field': fields.many2one('xml.export.field', 'Export Field', required=True, ondelete="restrict"),
        'openerp_field': fields.many2one('ir.model.fields', 'OpenERP Field'),
        'openerp_model': fields.many2one('ir.model', 'OpenERP Model'),
        'action': fields.selection(
            (
                ('field','Field Value'),
                ('compute','Empty/Compute Value'),
                ('attribute','Alter Attribute'),
                ('repeat','Repeat per record'),
                ('repeat_sub','Repeat per value'),
            ), string='Action', required=True),
        'code': fields.text('Code', help='Any custom code (python expression) you want to apply'),
        'include_code': fields.text('Include code', help='Python expression which will toggle inclusion in export'),
        'notes': fields.text('Notes'),
        'sequence': fields.related('xml_field','sequence', type='integer', string='Sequence', readonly=True),
    }

    _defaults = {
        'include_code': 'True',
    }
xml_profile_line()

# vim:sts=4:et
