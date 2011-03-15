# Copyright 2011, Agaplan

import time
import logging
import base64
#from xml.dom import minidom
from lxml import etree
from copy import deepcopy

from osv import osv, fields
from tools.translate import _

log = logging.getLogger('xml_export_wizard')

class xml_export_wizard(osv.osv_memory):
    _name = "xml.export.wizard"

    _columns = {
        'profile_id': fields.many2one('xml.profile', 'Profile', required=True),
        'res_model': fields.char('Export model', size=64, required=True),
        'res_id': fields.integer('Export ID'),
        'data_xml': fields.binary('Output file', readonly=True),
        'errors': fields.text('Errors', readonly=True),
    }

    def default_get(self, cr, uid, names, context=None):
        if context is None:
            context = {}
        res = {}

        if 'profile_id' in names:
            res['profile_id'] = context.get('xml_profile')
        if 'res_model' in names:
            res['res_model'] = context.get('active_model')
        if 'res_id' in names:
            res['res_id'] = context.get('active_id')
        if 'data_xml' in names and 'xml_profile' in names:
            xml_data = self.get_data_xml(cr, uid, res, context)
            res['data_xml'] = base64.b64encode(xml_data)
        return res

    def get_data_xml(self, cr, uid, data, context=None):
        if context is None:
            context = {}

        try:
            profile = self.pool.get('xml.profile').browse(cr, uid, data['profile_id'])
            log.info("XML Export of %s, records : %s using %s profile" % (data['res_model'], data['res_id'], profile.name))
            nsmap = {}
            if profile.export_id.namespace:
                nsmap[None] = profile.export_id.namespace
            if profile.export_id.schema:
                nsmap['xsi'] = profile.export_id.schema

            def get_next_line(line, sub_line, context=None):
#               log.info("Finding next line for %s" % sub_line.name)
                line_obj = self.pool.get('xml.profile.line')
                lines = line_obj.search(cr, uid, [('profile_id','=',line.profile_id.id), ('xml_field','=',sub_line.id)], context=context)
                for tnew_line in line_obj.browse(cr, uid, lines, context=context):
                    log.debug("Yielding %s" % tnew_line)
                    yield tnew_line

            def parse_line(element, line, parent=None, model=None, cur_id=None, context=None):
                log.debug("%s, action %s, model %s, id %s" % (element.tag, line.action, model, cur_id))
                # First we find where the original element is (parents etc)
#               parent = parent.xpath( path ) and parent.xpath( path ) or None
                objects = None
                field = None

                if model and cur_id:
                    objects = self.pool.get(model).browse(cr, uid, cur_id, context=context)
                    log.debug("Browsed on objects %s" % (objects))
                if objects and line.openerp_field:
                    field = getattr(objects, line.openerp_field.name)
                    log.debug("Field value of <%s> %s : %s" % (element.tag, line.openerp_field.name, field))

                if line.action == 'compute':
                    try:
                        value = eval( str(line.code) )
                        element.text = "%s" % (value or '')
                    except Exception, e:
                        raise osv.except_osv(_("Compute Error"), _("The code for field %s failed with following message:\n%s") % (element.tag, e))

                if line.action == 'field':
                    element.text = "%s" % (field or '')

                if line.action == 'attribute':
                    value = eval( str(line.code) )
                    log.debug("Attribute result: %s" % value)

                    # No duplicates ! (was duplicated by parent)
                    parent.remove( element )
                    # Find the original
                    element = parent.find( line.xml_field.name )
                    # Set attribute
                    element.set( value['key'], value['value'] )
                    return # When setting attributes we dont want to loop on child fields

                if line.xml_field.child_ids and element.getparent(): # We can skip children if the element has been disconnected
                    # Checking what kind of loop is needed
                    if line.action in ['repeat', 'repeat_sub']:
                        if line.action == 'repeat' and not field:
                            # This way it will loop on the records
                            field = [objects]

                        # Remove our element, as we will re-create them on the fly
                        parent.remove( element )

                        log.info("%s on following ids: %s" % (line.action, field))
                        new_model = line.openerp_field.relation or line.openerp_model.model
                        for record in field:
                            record_tag = etree.SubElement( parent, element.tag )
                            log.info("Handling record %s" % record)
                            for sub_line in line.xml_field.child_ids:
                                for new_line in get_next_line( line, sub_line ):
                                    new_tag = etree.SubElement( record_tag, sub_line.name )
                                    log.info("Creating tag %s" % new_tag.tag)
                                    parse_line( new_tag, new_line, record_tag, new_model, record.id, context)
                    else:
                        for sub_line in line.xml_field.child_ids:
                            for new_line in get_next_line( line, sub_line ):
                                # Its in the profile, so create it if it passes include_code test
                                try:
                                    include = eval( str( new_line.include_code ) )
                                    if not include: continue
                                except Exception, e:
                                    raise osv.except_osv(_("Compute Error"), _("Error while running include_code for %s in child %s\n%s") % (line.xml_field.name, sub_line.name, e))

                                new_tag = etree.SubElement( element, sub_line.name )
                                log.info("Creating tag %s" % new_tag.tag)
                                parse_line( new_tag, new_line, element, model, cur_id, context )
            # END OF PARSE_LINE

            # Now we loop over the lines again and duplicate where needed
            for line in profile.lines:
                if line.xml_field.parent_id: continue # Skip non-root items

                # Create our root node
                doc = etree.Element( profile.export_id.root, nsmap=nsmap )
                cts = etree.SubElement( doc, line.xml_field.name )
                parse_line( cts, line, doc, data['res_model'], data['res_id'], context )

            result = "%s%s%s" % (
                profile.export_id.head_xml or '',
                etree.tounicode(doc, pretty_print=False),
                profile.export_id.feet_xml or '',
            )

            return result
        except Exception, e:
            log.error("Error while exporting xml data")
            raise

    def action_export(self, cr, uid, ids, context=None):
        """
            Function is called from view when there was no xml_profile in the context
        """
        me = self.browse(cr, uid, ids[0], context)
        data = {
            'profile_id': me.profile_id.id,
            'res_model': me.res_model,
            'res_id': me.res_id,
        }
        xml_data = self.get_data_xml(cr, uid, data, context)
        errors = ""

        # Validation time
        profile = me.profile_id
        schema_file = None
        schema = None

        if profile.export_id.validation_file:
            schema_file = base64.b64decode( profile.export_id.validation_file )

        if schema_file:
            if profile.export_id.validation_type == 'xsd':
                schema = etree.XMLSchema( etree.fromstring( schema_file ) )
            elif profile.export_id.validation_type == 'rng':
                schema = etree.RelaxNG( etree.fromstring( schema_file ) )
            elif profile.export_id.validation_type == 'schematron':
                schema = etree.Schematron( etree.fromstring( schema_file ) )

        if schema:
            status = schema.validate( etree.fromstring( xml_data ) )
            print "Validation status:",status
            if not status:
                errors = "\n".join([str(x) for x in schema.error_log])

        self.write(cr, uid, ids, {
            'data_xml': base64.b64encode(xml_data),
            'errors': errors,
        }, context=context)
        return True
xml_export_wizard()

# vim:sts=4:et
