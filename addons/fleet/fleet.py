# -*- coding: utf-8 -*-
from itertools import chain
from osv import osv, fields
import time
import datetime
import tools
from osv.orm import except_orm
from tools.translate import _
from dateutil.relativedelta import relativedelta
############################
############################
#Vehicle.cost class
############################
############################

class fleet_vehicle_cost(osv.Model):
    _name = 'fleet.vehicle.cost'
    _description = 'Cost of vehicle'
    _order = 'date desc, vehicle_id asc'

    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return []
        reads = self.browse(cr, uid, ids, context=context)
        res = []
        for record in reads:
            if record.vehicle_id.license_plate:
                name = record.vehicle_id.license_plate
            if record.cost_subtype.name:
                name = name + ' / '+ record.cost_subtype.name
            if record.date:
                name = name + ' / '+ record.date
            res.append((record.id, name))
        return res

    def _cost_name_get_fnc(self, cr, uid, ids, name, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    _columns = {
        'name' : fields.function(_cost_name_get_fnc, type="char", string='Name', store=True),
        #'name' : fields.char('Name',size=32),
        'vehicle_id': fields.many2one('fleet.vehicle', 'Vehicle', required=True, help='Vehicle concerned by this fuel log'),
        'cost_subtype': fields.many2one('fleet.service.type', 'Type', required=False, help='Cost type purchased with this cost'),
        'amount': fields.float('Total Price'),
        'cost_type' : fields.selection([('contract', 'Contract'),('services','Services'),('fuel','Fuel'),('other','Other')], 'Category of the cost', help='For internal purpose only',required=True),
        'parent_id': fields.many2one('fleet.vehicle.cost', 'Parent', required=False, help='Parent cost to this current cost'),
        'cost_ids' : fields.one2many('fleet.vehicle.cost', 'parent_id', 'Included Services'),

        'date' :fields.date('Date',help='Date when the cost has been executed'),

        'contract_id' : fields.many2one('fleet.vehicle.log.contract', 'Contract', required=False, help='Contract attached to this cost'),
        'auto_generated' : fields.boolean('automatically generated',readonly=True,required=True)
    }

    _defaults ={
        'parent_id':None,
        'auto_generated' : False,
        'cost_type' : 'other',
    }

    

    def create(self, cr, uid, data, context=None):
        if 'parent_id' in data and data['parent_id']:
            parent = self.browse(cr, uid, data['parent_id'], context=context)
            data['vehicle_id'] = parent.vehicle_id.id
            data['date'] = parent.date
            data['cost_type'] = parent.cost_type
        if 'contract_id' in data and data['contract_id']:
            contract = self.pool.get('fleet.vehicle.log.contract').browse(cr, uid, data['contract_id'], context=context)
            data['vehicle_id'] = contract.vehicle_id.id
            data['cost_subtype'] = contract.cost_subtype.id
            data['cost_type'] = contract.cost_type
        if not('cost_type' in data and data['cost_type']):
            data['cost_type'] = 'other'
        cost_id = super(fleet_vehicle_cost, self).create(cr, uid, data, context=context)
        return cost_id

############################
############################
#Vehicle.tag class
############################
############################

class fleet_vehicle_tag(osv.Model):
    _name = 'fleet.vehicle.tag'
    _columns = {
        'name': fields.char('Name', required=True, translate=True),
    }

############################
############################
#Vehicle.state class
############################
############################

class fleet_vehicle_state(osv.Model):
    _name = 'fleet.vehicle.state'
    _columns = {
        'name': fields.char('Name', required=True),
        'sequence': fields.integer('Order',help="Used to order the note stages")
    }
    _order = 'sequence asc'
    _sql_constraints = [('fleet_state_name_unique','unique(name)','State name already exists')]


############################
############################
#Vehicle.model class
############################
############################

class fleet_vehicle_model(osv.Model):

    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return []
        reads = self.browse(cr, uid, ids, context=context)
        res = []
        for record in reads:
            name = record.modelname
            if record.brand.name:
                name = record.brand.name+' / '+name
            res.append((record.id, name))
        return res

    def _model_name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    def on_change_brand(self, cr, uid, ids, model_id, context=None):

        if not model_id:
            return {}

        brand = self.pool.get('fleet.vehicle.model.brand').browse(cr, uid, model_id, context=context)

        return {
            'value' : {
                'image' : brand.image,
            }
        }

    _name = 'fleet.vehicle.model'
    _description = 'Model of a vehicle'

    _columns = {
        'name' : fields.function(_model_name_get_fnc, type="char", string='Name', store=True),
        'modelname' : fields.char('Model name', size=32, required=True), 
        'brand' : fields.many2one('fleet.vehicle.model.brand', 'Model Brand', required=True, help='Brand of the vehicle'),
        'vendors': fields.many2many('res.partner','fleet_vehicle_model_vendors','model_id', 'partner_id',string='Vendors',required=False),
        'image': fields.related('brand','image',type="binary",string="Logo",store=False),
        'image_medium': fields.related('brand','image_medium',type="binary",string="Logo",store=False),
        'image_small': fields.related('brand','image_small',type="binary",string="Logo",store=False),
    }

############################
############################
#Vehicle.brand class
############################
############################

class fleet_vehicle_model_brand(osv.Model):
    _name = 'fleet.vehicle.model.brand'
    _description = 'Brand model of the vehicle'

    _order = 'name asc'

    def _get_image(self, cr, uid, ids, name, args, context=None):
        result = dict.fromkeys(ids, False)
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = tools.image_get_resized_images(obj.image)
        return result
    
    def _set_image(self, cr, uid, id, name, value, args, context=None):
        return self.write(cr, uid, [id], {'image': tools.image_resize_image_big(value)}, context=context)

    _columns = {
        'name' : fields.char('Brand Name',size=32, required=True),

        'image': fields.binary("Logo",
            help="This field holds the image used as logo for the brand, limited to 1024x1024px."),
        'image_medium': fields.function(_get_image, fnct_inv=_set_image,
            string="Medium-sized photo", type="binary", multi="_get_image",
            store = {
                'fleet.vehicle.model.brand': (lambda self, cr, uid, ids, c={}: ids, ['image'], 10),
            },
            help="Medium-sized logo of the brand. It is automatically "\
                 "resized as a 128x128px image, with aspect ratio preserved. "\
                 "Use this field in form views or some kanban views."),
        'image_small': fields.function(_get_image, fnct_inv=_set_image,
            string="Smal-sized photo", type="binary", multi="_get_image",
            store = {
                'fleet.vehicle.model.brand': (lambda self, cr, uid, ids, c={}: ids, ['image'], 10),
            },
            help="Small-sized photo of the brand. It is automatically "\
                 "resized as a 64x64px image, with aspect ratio preserved. "\
                 "Use this field anywhere a small image is required."),
    }

############################
############################
#Vehicle class
############################
############################


class fleet_vehicle(osv.Model):

    _inherit = 'mail.thread'

    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return []
        reads = self.browse(cr, uid, ids, context=context)
        res = []
        for record in reads:
            if record.license_plate:
                name = record.license_plate
            if record.model_id.modelname:
                name = record.model_id.modelname + ' / ' + name
            if record.model_id.brand.name:
                name = record.model_id.brand.name+' / '+ name
            res.append((record.id, name))
        return res

    def _vehicle_name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    def act_show_log_services(self, cr, uid, ids, context=None):
        """ This opens log view to view and add new log for this vehicle
            @return: the service log view
        """
        res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid ,'fleet','fleet_vehicle_log_services_act', context)
        res['context'] = {
            'default_vehicle_id': ids[0]
        }
        res['domain']=[('vehicle_id','=', ids[0])]
        return res

    def act_show_log_contract(self, cr, uid, ids, context=None):
        """ This opens log view to view and add new log for this vehicle
            @return: the contract log view
        """
        res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid ,'fleet','fleet_vehicle_log_contract_act', context)
        res['context'] = {
            'default_vehicle_id': ids[0]
        }
        res['domain']=[('vehicle_id','=', ids[0])]
        return res

    def act_show_log_fuel(self, cr, uid, ids, context=None):
        """ This opens log view to view and add new log for this vehicle
            @return: the fuel log view
        """
        res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid ,'fleet','fleet_vehicle_log_fuel_act', context)
        res['context'] = {
            'default_vehicle_id': ids[0]
        }
        res['domain']=[('vehicle_id','=', ids[0])]
        return res

    def act_show_log_cost(self, cr, uid, ids, context=None):
        """ This opens log view to view and add new log for this vehicle
            @return: the costs log view
        """
        res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid ,'fleet','fleet_vehicle_costs_act', context)
        res['context'] = {
            'default_vehicle_id': ids[0],
            'search_default_parent_false' : True
        }
        res['domain']=[('vehicle_id','=', ids[0])]
        return res

    def act_show_log_odometer(self, cr, uid, ids, context=None):
        """ This opens log view to view and add new log for this vehicle
            @return: the odometer log view
        """
        res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid ,'fleet','fleet_vehicle_odometer_act', context)
        res['context'] = {
            'default_vehicle_id': ids[0]
        }
        res['domain']=[('vehicle_id','=', ids[0])]
        return res

    def _get_odometer(self, cr, uid, ids, odometer_id, arg, context):
        res = dict.fromkeys(ids, False)
        for record in self.browse(cr,uid,ids,context=context):    
            ids = self.pool.get('fleet.vehicle.odometer').search(cr,uid,[('vehicle_id','=',record.id)],limit=1, order='value desc')
            if len(ids) > 0:
                res[record.id] = str(self.pool.get('fleet.vehicle.odometer').browse(cr,uid,ids[0],context=context).value)
            else:
                res[record.id] = str(0)
        return res

    def _set_odometer(self, cr, uid, id, name, value, args=None, context=None):
        if value:
            try:
                value = float(value)
            except ValueError:
                #_logger.exception(value+' is not a correct odometer value. Please, fill a float for this field')
                raise except_orm(_('Error!'), value+' is not a correct odometer value. Please, fill a float for this field')
            
            date = time.strftime('%Y-%m-%d')
            data = {'value' : value,'date' : date,'vehicle_id' : id}
            odometer_id = self.pool.get('fleet.vehicle.odometer').create(cr, uid, data, context=context)
            return value
        self.write(cr, uid, id, {'odometer_id': ''})
        return False  

    def str_to_date(self,strdate):
        return datetime.datetime(int(strdate[:4]),int(strdate[5:7]),int(strdate[8:]))

    def get_overdue_contract_reminder_fnc(self,cr,uid,ids,context=None):
        if context is None:
            context={}
        if not ids:
            return dict([])
        reads = self.browse(cr,uid,ids,context=context)
        res=[]
        
        for record in reads:
            overdue=0
            if (record.log_contracts):
                for element in record.log_contracts:
                    if (element.state=='open' and element.expiration_date):
                        current_date_str=time.strftime('%Y-%m-%d')
                        due_time_str=element.expiration_date
                            #due_time_str=element.browse()
                        current_date=self.str_to_date(current_date_str)
                        due_time=self.str_to_date(due_time_str)
             
                        diff_time=int((due_time-current_date).days)
                        if diff_time<0:
                            overdue = overdue +1;
                res.append((record.id,overdue))
            else:
                res.append((record.id,0))

        return dict(res)

    def get_overdue_contract_reminder(self,cr,uid,ids,prop,unknow_none,context=None):
        res = self.get_overdue_contract_reminder_fnc(cr, uid, ids, context=context)
        return res

    def get_next_contract_reminder_fnc(self,cr,uid,ids,context=None):
        if context is None:
            context={}
        if not ids:
            return dict([])
        reads = self.browse(cr,uid,ids,context=context)
        res=[]

        for record in reads:
            due_soon=0
            if (record.log_contracts):
                for element in record.log_contracts:
                    if (element.state=='open' and element.expiration_date):
                        current_date_str=time.strftime('%Y-%m-%d')
                        due_time_str=element.expiration_date
                            #due_time_str=element.browse()
                        current_date=self.str_to_date(current_date_str)
                        due_time=self.str_to_date(due_time_str)
             
                        diff_time=int((due_time-current_date).days)
                        if diff_time<15 and diff_time>=0:
                            due_soon = due_soon +1;
                res.append((record.id,due_soon))
            else:
                res.append((record.id,0))
        
        return dict(res)

    def _search_get_overdue_contract_reminder(self, cr, uid, obj, name, args, context):
        res = []
        for field, operator, value in args:
            #assert field == name
            vehicle_ids = self.search(cr, uid, [])
            renew_ids = self.get_overdue_contract_reminder_fnc(cr,uid,vehicle_ids,context=context)
            res_ids = []
            for renew_key,renew_value in renew_ids.items():
                if eval(str(renew_value) + " " + str(operator) + " " + str(value)):
                    res_ids.append(renew_key)
            res.append(('id', 'in', res_ids))      
        return res
    
    def _search_contract_renewal_due_soon(self, cr, uid, obj, name, args, context):
        res = []
        for field, operator, value in args:
            #assert field == name
            vehicle_ids = self.search(cr, uid, [])
            renew_ids = self.get_next_contract_reminder_fnc(cr,uid,vehicle_ids,context=context)
            res_ids = []
            for renew_key,renew_value in renew_ids.items():
                if eval(str(renew_value) + " " + str(operator) + " " + str(value)):
                    res_ids.append(renew_key)
            res.append(('id', 'in', res_ids))      
        return res

    def get_next_contract_reminder(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.get_next_contract_reminder_fnc(cr, uid, ids, context=context)
        return res

    def get_contract_renewal_names(self,cr,uid,ids,function_name,args,context=None):
        if not ids:
            return dict([])
        reads = self.browse(cr,uid,ids,context=context)
        res=[]
        for record in reads:
            if (record.log_contracts):
                ids = self.pool.get('fleet.vehicle.log.contract').search(cr,uid,[('vehicle_id','=',record.id),('state','=','open')],limit=1,order='expiration_date asc')
                if len(ids) > 0:
                    res.append((record.id,self.pool.get('fleet.vehicle.log.contract').browse(cr,uid,ids[0],context=context).cost_subtype.name))
            else:
                res.append((record.id,''))
        return dict(res)

    def get_total_contract_reminder(self,cr,uid,ids,prop,unknow_none,context=None):
        if context is None:
            context={}
        if not ids:
            return dict([])
        reads = self.browse(cr,uid,ids,context=context)
        res=[]

        for record in reads:
            due_soon=0
            if (record.log_contracts):
                for element in record.log_contracts:
                    if (element.state=='open' and element.expiration_date):
                        current_date_str=time.strftime('%Y-%m-%d')
                        due_time_str=element.expiration_date

                        current_date=self.str_to_date(current_date_str)
                        due_time=self.str_to_date(due_time_str)
             
                        diff_time=int((due_time-current_date).days)
                        if diff_time<15:
                            due_soon = due_soon +1;
                if due_soon>0:
                    due_soon=due_soon-1
                res.append((record.id,due_soon))
            else:
                res.append((record.id,0))
        
        return dict(res)

    def run_scheduler(self,cr,uid,context=None):
        ids = self.pool.get('fleet.vehicle').search(cr, uid, [], offset=0, limit=None, order=None,context=None, count=False)
        nexts = self.get_next_contract_reminder_fnc(cr,uid,ids,context=context)
        overdues = self.get_overdue_contract_reminder_fnc(cr,uid,ids,context=context)
        for key,value in nexts.items():
            if value > 0 and overdues[key] > 0:
                self.message_post(cr, uid, [key], body=str(value) + ' contract(s) has to be renewed soon and '+str(overdues[key])+' contract(s) is (are) overdued', context=context)
            elif value > 0:
                self.message_post(cr, uid, [key], body=str(value) + ' contract(s) has to be renewed soon!', context=context)
            elif overdues[key] > 0 : 
                self.message_post(cr, uid, [key], body=str(overdues[key]) + ' contract(s) is(are) overdued!', context=context)
        return True

    def _get_default_state(self, cr, uid, context):
        try:
            model, model_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'fleet', 'vehicle_state_active')
        except ValueError:
            model_id = False
        return model_id

    _name = 'fleet.vehicle'
    _description = 'Fleet Vehicle'
    #_order = 'contract_renewal_overdue desc, contract_renewal_due_soon desc'
    _order= 'license_plate asc'
    _columns = {
        'name' : fields.function(_vehicle_name_get_fnc, type="char", string='Name', store=True),

        'company_id': fields.many2one('res.company', 'Company'),
        'license_plate' : fields.char('License Plate', size=32, required=True, help='License plate number of the vehicle (ie: plate number for a car)'),
        'vin_sn' : fields.char('Chassis Number', size=32, required=False, help='Unique number written on the vehicle motor (VIN/SN number)'),
        'driver' : fields.many2one('res.partner', 'Driver',required=False, help='Driver of the vehicle'),
        'model_id' : fields.many2one('fleet.vehicle.model', 'Model', required=True, help='Model of the vehicle'),
        'log_fuel' : fields.one2many('fleet.vehicle.log.fuel','vehicle_id', 'Fuel Logs'),
        'log_services' : fields.one2many('fleet.vehicle.log.services','vehicle_id', 'Services Logs'),
        'log_contracts' : fields.one2many('fleet.vehicle.log.contract','vehicle_id', 'Contracts'),
        'acquisition_date' : fields.date('Acquisition Date', required=False, help='Date when the vehicle has been bought'),
        'color' : fields.char('Color',size=32, help='Color of the vehicle'),
        'state': fields.many2one('fleet.vehicle.state', 'State', help='Current state of the vehicle',ondelete="set null"),
        'location' : fields.char('Location',size=32, help='Location of the vehicle (garage, ...)'),
        'seats' : fields.integer('Seats Number', help='Number of seats of the vehicle'),
        'doors' : fields.integer('Doors Number', help='Number of doors of the vehicle'),
        'tag_ids' :fields.many2many('fleet.vehicle.tag','fleet_vehicle_vehicle_tag_rel','vehicle_tag_id','tag_id','Tags'),

        'odometer' : fields.function(_get_odometer,fnct_inv=_set_odometer,type='char',string='Odometer Value',store=False,help='Odometer measure of the vehicle at the moment of this log'),
        'odometer_unit': fields.selection([('kilometers', 'Kilometers'),('miles','Miles')], 'Odometer Unit', help='Unit of the odometer ',required=True),

        'transmission' : fields.selection([('manual', 'Manual'),('automatic','Automatic')], 'Transmission', help='Transmission Used by the vehicle',required=False),
        'fuel_type' : fields.selection([('gasoline', 'Gasoline'),('diesel','Diesel'),('electric','Electric'),('hybrid','Hybrid')], 'Fuel Type', help='Fuel Used by the vehicle',required=False),
        'horsepower' : fields.integer('Horsepower',required=False),
        'horsepower_tax': fields.float('Horsepower Taxation'),
        'power' : fields.integer('Power (kW)',required=False,help='Power in kW of the vehicle'),
        'co2' : fields.float('CO2 Emissions',required=False,help='CO2 emissions of the vehicle'),

        'image': fields.related('model_id','image',type="binary",string="Logo",store=False),
        'image_medium': fields.related('model_id','image_medium',type="binary",string="Logo",store=False),
        'image_small': fields.related('model_id','image_small',type="binary",string="Logo",store=False),

        'contract_renewal_due_soon' : fields.function(get_next_contract_reminder,fnct_search=_search_contract_renewal_due_soon,type="integer",string='Contracts to renew',store=False),
        'contract_renewal_overdue' : fields.function(get_overdue_contract_reminder,fnct_search=_search_get_overdue_contract_reminder,type="integer",string='Contracts Overdued',store=False),
        'contract_renewal_name' : fields.function(get_contract_renewal_names,type="text",string='Name of contract to renew soon',store=False),
        'contract_renewal_total' : fields.function(get_total_contract_reminder,type="integer",string='Total of contracts due or overdue minus one',store=False),

        'car_value': fields.float('Car Value', help='Value of the bought vehicle'),
        #'leasing_value': fields.float('Leasing value',help='Value of the leasing(Monthly, usually'),
        }

    _defaults = {
        'doors' : 5,
        'odometer_unit' : 'kilometers',
        'state' : _get_default_state,
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}

        default.update({
        #    'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.orderpoint') or '',
            #'log_ids':[],
            'log_fuel':[],
            'log_contracts':[],
            'log_services':[],
            'tag_ids':[],
            'vin_sn':'',
        })
        return super(fleet_vehicle, self).copy(cr, uid, id, default, context=context)

    def on_change_model(self, cr, uid, ids, model_id, context=None):

        if not model_id:
            return {}

        model = self.pool.get('fleet.vehicle.model').browse(cr, uid, model_id, context=context)

        return {
            'value' : {
                'image' : model.image,
            }
        }
    def create(self, cr, uid, data, context=None):
        vehicle_id = super(fleet_vehicle, self).create(cr, uid, data, context=context)
        try:
            vehicle = self.browse(cr, uid, vehicle_id, context=context)
            self.message_post(cr, uid, [vehicle_id], body='Vehicle %s has been added to the fleet!' % (vehicle.license_plate), context=context)
        except:
            pass # group deleted: do not push a message
        return vehicle_id

    def write(self, cr, uid, ids, vals, context=None):
        changes = []
        if 'driver' in vals:
            value = self.pool.get('res.partner').browse(cr,uid,vals['driver'],context=context).name
            olddriver = self.browse(cr, uid, ids, context)[0].driver
            if olddriver:
                olddriver = olddriver.name
            else:
                olddriver = 'None'
            changes.append('Driver: from \'' + olddriver + '\' to \'' + value+'\'')
        if 'state' in vals:
            value = self.pool.get('fleet.vehicle.state').browse(cr,uid,vals['state'],context=context).name
            oldstate = self.browse(cr, uid, ids, context)[0].state
            if oldstate:
                oldstate=oldstate.name
            else:
                oldstate = 'None'
            changes.append('State: from \'' + oldstate + '\' to \'' + value+'\'')
        if 'license_plate' in vals:
            old_license_plate = self.browse(cr, uid, ids, context)[0].license_plate
            if not old_license_plate:
                old_license_plate = 'None'
            changes.append('License Plate: from \'' + old_license_plate + '\' to \'' + vals['license_plate']+'\'')   
       
        vehicle_id = super(fleet_vehicle,self).write(cr, uid, ids, vals, context)

        try:
            if len(changes) > 0:
                self.message_post(cr, uid, [self.browse(cr, uid, ids, context)[0].id], body=", ".join(changes), context=context)
        except Exception as e:
            print e
            pass
        return vehicle_id

############################
############################
#Vehicle.odometer class
############################
############################

class fleet_vehicle_odometer(osv.Model):
    _name='fleet.vehicle.odometer'
    _description='Odometer log for a vehicle'

    _order='date desc'

    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return []
        reads = self.browse(cr, uid, ids, context=context)
        res = []
        for record in reads:
            if record.vehicle_id.name:
                name = str(record.vehicle_id.name)
            if record.date:
                name = name+ ' / '+ str(record.date)
            res.append((record.id, name))
        return res

    def _vehicle_log_name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)
    def on_change_vehicle(self, cr, uid, ids, vehicle_id, context=None):

        if not vehicle_id:
            return {}

        odometer_unit = self.pool.get('fleet.vehicle').browse(cr, uid, vehicle_id, context=context).odometer_unit

        return {
            'value' : {
                'unit' : odometer_unit,
            }
        }

    _columns = {
        'name' : fields.function(_vehicle_log_name_get_fnc, type="char", string='Name', store=True),

        'date' : fields.date('Date'),
        'value' : fields.float('Odometer Value',group_operator="max"),
        'vehicle_id' : fields.many2one('fleet.vehicle', 'Vehicle', required=True),
        'unit': fields.related('vehicle_id','odometer_unit',type="char",string="Unit",store=False, readonly=True),
        
    }
    _defaults = {
        'date' : time.strftime('%Y-%m-%d')
    }

############################
############################
#Vehicle.log classes
############################
############################


############################
############################
#Vehicle.log.fuel class
############################
############################


class fleet_vehicle_log_fuel(osv.Model):

    #_inherits = {'fleet.vehicle.odometer': 'odometer_id'}
    _inherits = {'fleet.vehicle.cost': 'cost_id'}

    def on_change_vehicle(self, cr, uid, ids, vehicle_id, context=None):

        if not vehicle_id:
            return {}

        odometer_unit = self.pool.get('fleet.vehicle').browse(cr, uid, vehicle_id, context=context).odometer_unit

        return {
            'value' : {
                'odometer_unit' : odometer_unit,
            }
        }

    def on_change_liter(self, cr, uid, ids, liter, price_per_liter, amount, context=None):

        if liter > 0 and price_per_liter > 0:
            return {'value' : {'amount' : float(liter) * float(price_per_liter),}}
        elif liter > 0 and amount > 0:
            return {'value' : {'price_per_liter' : float(amount) / float(liter),}}
        elif price_per_liter > 0 and amount > 0:
            return {'value' : {'liter' : float(amount) / float(price_per_liter),}}
        else :
            return {}

    def on_change_price_per_liter(self, cr, uid, ids, liter, price_per_liter, amount, context=None):

        liter = float(liter);
        price_per_liter = float(price_per_liter);
        if price_per_liter > 0 and liter > 0:
            return {'value' : {'amount' : float(liter) * float(price_per_liter),}}
        elif price_per_liter > 0 and amount > 0:
            return {'value' : {'liter' : float(amount) / float(price_per_liter),}}
        elif liter > 0 and amount > 0:
            return {'value' : {'price_per_liter' : float(amount) / float(liter),}}
        else :
            return {}

    def on_change_amount(self, cr, uid, ids, liter, price_per_liter, amount, context=None):

        if amount > 0 and liter > 0:
            return {'value' : {'price_per_liter' : float(amount) / float(liter),}}
        elif amount > 0 and price_per_liter > 0:
            return {'value' : {'liter' : float(amount) / float(price_per_liter),}}
        elif liter > 0 and price_per_liter > 0:
            return {'value' : {'amount' : float(liter) * float(price_per_liter),}}
        else :
            return {}
        
    def _get_odometer(self, cr, uid, ids, odometer_id, arg, context):
        res = dict.fromkeys(ids, False)
        for record in self.browse(cr,uid,ids,context=context):
            if record.odometer_id:
                res[record.id] = record.odometer_id.value
        return res

    def _set_odometer(self, cr, uid, id, name, value, args=None, context=None):
        if value:
            try:
                value = float(value)
            except ValueError:
                #_logger.exception(value+' is not a correct odometer value. Please, fill a float for this field')
                raise except_orm(_('Error!'), value+' is not a correct odometer value. Please, fill a float for this field')
               
            date = self.browse(cr, uid, id, context=context).date
            if not(date):
                date = time.strftime('%Y-%m-%d')
            vehicle_id = self.browse(cr, uid, id, context=context).vehicle_id
            data = {'value' : value,'date' : date,'vehicle_id' : vehicle_id.id}
            odometer_id = self.pool.get('fleet.vehicle.odometer').create(cr, uid, data, context=context)
            self.write(cr, uid, id, {'odometer_id': odometer_id})
            return value
        self.write(cr, uid, id, {'odometer_id': ''})
        return False

    def _get_default_service_type(self, cr, uid, context):
        try:
            model, model_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'fleet', 'type_service_refueling')
        except ValueError:
            model_id = False
        return model_id

    _name = 'fleet.vehicle.log.fuel'

    _columns = {
        #'name' : fields.char('Name',size=64),
        'liter' : fields.float('Liter'),
        'price_per_liter' : fields.float('Price Per Liter'),
        'purchaser_id' : fields.many2one('res.partner', 'Purchaser',domain="['|',('customer','=',True),('employee','=',True)]"),
        'inv_ref' : fields.char('Invoice Reference', size=64),
        'vendor_id' : fields.many2one('res.partner', 'Supplier', domain="[('supplier','=',True)]"),
        'notes' : fields.text('Notes'),
        'odometer_id' : fields.many2one('fleet.vehicle.odometer', 'Odometer', required=False, help='Odometer measure of the vehicle at the moment of this log'),
        'odometer' : fields.function(_get_odometer,fnct_inv=_set_odometer,type='char',string='Odometer',store=False),
        'odometer_unit': fields.related('vehicle_id','odometer_unit',type="char",string="Unit",store=False, readonly=True),
        'cost_amount': fields.related('cost_id','amount',type="float",string="Amount",store=True, readonly=True),
    }
    _defaults = {
        'purchaser_id': lambda self, cr, uid, ctx: uid,
        'date' : time.strftime('%Y-%m-%d'),
        'cost_subtype': _get_default_service_type,
    }
    def create(self, cr, uid, data, context=None):
        data['cost_type'] = 'fuel'
        cost_id = super(fleet_vehicle_log_fuel, self).create(cr, uid, data, context=context)
        return cost_id

############################
############################
#Vehicle.log.service class
############################
############################


class fleet_vehicle_log_services(osv.Model):

    _inherits = {'fleet.vehicle.cost': 'cost_id'}

    def on_change_vehicle(self, cr, uid, ids, vehicle_id, context=None):

        if not vehicle_id:
            return {}

        odometer_unit = self.pool.get('fleet.vehicle').browse(cr, uid, vehicle_id, context=context).odometer_unit

        return {
            'value' : {
                'odometer_unit' : odometer_unit,
            }
        }

    def _get_odometer(self, cr, uid, ids, odometer_id, arg, context):
        res = dict.fromkeys(ids, False)
        for record in self.browse(cr,uid,ids,context=context):
            if record.odometer_id:
                res[record.id] = record.odometer_id.value
        return res

    def _set_odometer(self, cr, uid, id, name, value, args=None, context=None):
        if value:
            try:
                value = float(value)
            except ValueError:
                #_logger.exception(value+' is not a correct odometer value. Please, fill a float for this field')
                raise except_orm(_('Error!'), value+' is not a correct odometer value. Please, fill a float for this field')
               
            date = self.browse(cr, uid, id, context=context).date
            if not(date):
                date = time.strftime('%Y-%m-%d')
            vehicle_id = self.browse(cr, uid, id, context=context).vehicle_id
            data = {'value' : value,'date' : date,'vehicle_id' : vehicle_id.id}
            odometer_id = self.pool.get('fleet.vehicle.odometer').create(cr, uid, data, context=context)
            self.write(cr, uid, id, {'odometer_id': odometer_id})
            return value
        self.write(cr, uid, id, {'odometer_id': ''})
        return False

    def _get_default_service_type(self, cr, uid, context):
        try:
            model, model_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'fleet', 'type_service_service_8')
        except ValueError:
            model_id = False
        return model_id

    _name = 'fleet.vehicle.log.services'
    _columns = {

        #'name' : fields.char('Name',size=64),

        'purchaser_id' : fields.many2one('res.partner', 'Purchaser',domain="['|',('customer','=',True),('employee','=',True)]"),
        'inv_ref' : fields.char('Invoice Reference', size=64),
        'vendor_id' :fields.many2one('res.partner', 'Supplier', domain="[('supplier','=',True)]"),
        'notes' : fields.text('Notes'),

        'odometer_id' : fields.many2one('fleet.vehicle.odometer', 'Odometer', required=False, help='Odometer measure of the vehicle at the moment of this log'),
        'odometer' : fields.function(_get_odometer,fnct_inv=_set_odometer,type='char',string='Odometer Value',store=False),
        'odometer_unit': fields.related('vehicle_id','odometer_unit',type="char",string="Unit",store=False, readonly=True),
        'cost_amount': fields.related('cost_id','amount',type="float",string="Amount",store=True, readonly=True),
    }
    _defaults = {
        'purchaser_id': lambda self, cr, uid, ctx: uid,
        'date' : time.strftime('%Y-%m-%d'),
        'cost_subtype' : _get_default_service_type
    }
    def create(self, cr, uid, data, context=None):
        data['cost_type'] = 'services'
        cost_id = super(fleet_vehicle_log_services, self).create(cr, uid, data, context=context)
        return cost_id

############################
############################
#Vehicle.service.type class
############################
############################

class fleet_service_type(osv.Model):
    _name = 'fleet.service.type'
    _columns = {
        'name': fields.char('Name', required=True, translate=True),
        'category': fields.selection([('contract', 'Contract'), ('service', 'Service'),('both', 'Both')], 'Category',required=True, help='Choose wheter the service refer to contracts, vehicle services or both'),
    }
    #_defaults = {
    #    'category': 'both'
    #}

############################
############################
#Vehicle.log.contract class
############################
############################

class fleet_vehicle_log_contract(osv.Model):

    _inherits = {'fleet.vehicle.cost': 'cost_id'}

    def run_scheduler(self,cr,uid,context=None):

        d = datetime.date.today()
        #d = datetime.datetime(2012, 12, 01)

        contract_ids = self.pool.get('fleet.vehicle.log.contract').search(cr, uid, [('state','=','open')], offset=0, limit=None, order=None,context=None, count=False)
        deltas = {'yearly' : relativedelta(years=+1),'monthly' : relativedelta(months=+1),'weekly' : relativedelta(weeks=+1),'daily' : relativedelta(days=+1)}
        for contract in self.pool.get('fleet.vehicle.log.contract').browse(cr,uid,contract_ids,context=context):
            if not contract.start_date or contract.cost_frequency == 'no':
                break;
            if contract.generated_cost_ids != []:
                last_cost_id = self.pool.get('fleet.vehicle.cost').search(cr, uid, ['&',('contract_id','=',contract.id),('auto_generated','=',True)], offset=0, limit=1, order='date desc',context=None, count=False)
                last_cost_date = self.pool.get('fleet.vehicle.cost').browse(cr,uid,last_cost_id[0],context=None).date
                found = True
            else : 
                found = False
                last_cost_date = contract.start_date
            startdate = datetime.datetime.strptime(last_cost_date,'%Y-%m-%d').date() 
            if found:
                startdate += deltas.get(contract.cost_frequency)
            while (startdate < d) & (startdate < datetime.datetime.strptime(contract.expiration_date,'%Y-%m-%d').date()):
                data = {'amount' : contract.cost_generated,'date' : startdate.strftime('%Y-%m-%d'),'vehicle_id' : contract.vehicle_id.id,'cost_subtype' : contract.cost_subtype.id,'contract_id' : contract.id,'auto_generated' : True}
                print data
                cost_id = self.pool.get('fleet.vehicle.cost').create(cr, uid, data, context=context)
                startdate += deltas.get(contract.cost_frequency)
        return True
    
    def name_get(self, cr, uid, ids, context=None):
        if context is None:
            context = {} 
        if not ids:
            return []
        reads = self.browse(cr, uid, ids, context=context)
        res = []
        for record in reads:
            if record.vehicle_id.name:
                name = str(record.vehicle_id.name)
            if record.cost_subtype.name:
                name = name+ ' / '+ str(record.cost_subtype.name)
            if record.date:
                name = name+ ' / '+ record.date
            res.append((record.id, name))
        return res

    def _vehicle_contract_name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    def _get_odometer(self, cr, uid, ids, odometer_id, arg, context):
        res = dict.fromkeys(ids, False)
        for record in self.browse(cr,uid,ids,context=context):
            if record.odometer_id:
                res[record.id] = record.odometer_id.value
        return res

    def _set_odometer(self, cr, uid, id, name, value, args=None, context=None):
        if value:
            try:
                value = float(value)
            except ValueError:
                #_logger.exception(value+' is not a correct odometer value. Please, fill a float for this field')
                raise except_orm(_('Error!'), value+' is not a correct odometer value. Please, fill a float for this field')
               
            date = self.browse(cr, uid, id, context=context).date
            if not(date):
                date = time.strftime('%Y-%m-%d')
            vehicle_id = self.browse(cr, uid, id, context=context).vehicle_id
            data = {'value' : value,'date' : date,'vehicle_id' : vehicle_id.id}
            odometer_id = self.pool.get('fleet.vehicle.odometer').create(cr, uid, data, context=context)
            self.write(cr, uid, id, {'odometer_id': odometer_id})
            return value
        self.write(cr, uid, id, {'odometer_id': ''})
        return False

    def on_change_vehicle(self, cr, uid, ids, vehicle_id, context=None):

        if not vehicle_id:
            return {}

        odometer_unit = self.pool.get('fleet.vehicle').browse(cr, uid, vehicle_id, context=context).odometer_unit

        return {
            'value' : {
                'odometer_unit' : odometer_unit,
            }
        }

    def compute_next_year_date(self, strdate):
        oneyear=datetime.timedelta(days=365)
        curdate = self.str_to_date(strdate)
        nextyear=curdate+oneyear#int(strdate[:4])+1
        return str(nextyear)#+strdate[4:]

    def on_change_start_date(self, cr, uid, ids, strdate, enddate, context=None):
        
        if (strdate):
           
            return {'value' : {'expiration_date' : self.compute_next_year_date(strdate),}}
        else:
            return {}

    def str_to_date(self,strdate):
        return datetime.datetime(int(strdate[:4]),int(strdate[5:7]),int(strdate[8:]))

    def get_warning_date(self,cr,uid,ids,prop,unknow_none,context=None):
        if context is None:
            context={}
        if not ids:
            return dict([])
        reads = self.browse(cr,uid,ids,context=context)
        res=[]
        for record in reads:
            #if (record.reminder==True):
            if (record.expiration_date and record.state=='open'):
                today=self.str_to_date(time.strftime('%Y-%m-%d'))
                renew_date = self.str_to_date(record.expiration_date)
                diff_time=int((renew_date-today).days)
                if (diff_time<=0):
                    res.append((record.id,0))
                else:
                    res.append((record.id,diff_time))
            else:
                res.append((record.id,-1))
            #else:
            #    res.append((record.id,-1))
        return dict(res)

    def act_renew_contract(self,cr,uid,ids,context=None):
        contracts = self.browse(cr,uid,ids,context=context)
        res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid ,'fleet','act_renew_contract', context)
        for element in contracts:
            temp = []
            temp.append(('default_vehicle_id',element.vehicle_id.id))
            temp.append(('default_cost_subtype',element.cost_subtype.id))
            temp.append(('default_amount',element.amount))
            temp.append(('default_odometer_id',element.odometer_id.id))
            temp.append(('default_odometer_unit',element.odometer_unit))
            temp.append(('default_insurer_id',element.insurer_id.id))
            cost_temp = []
            for costs in element.cost_ids:
                cost_temp.append(costs.id)
            temp.append(('default_cost_ids',cost_temp))
            temp.append(('default_date',time.strftime('%Y-%m-%d')))
            temp.append(('default_start_date',str(self.str_to_date(element.expiration_date)+datetime.timedelta(days=1))))
            temp.append(('default_purchaser_id',element.purchaser_id.id))
            temp.append(('default_ins_ref',element.ins_ref))
            temp.append(('default_state','open'))
            temp.append(('default_notes',element.notes))
            temp.append(('default_cost_frequency',element.cost_frequency))
            generated_cost = []
            for gen_cost in element.generated_cost_ids:
                generated_cost.append(gen_cost.id)
            temp.append(('default_generated_cost_ids',generated_cost))

            #compute end date
            startdate = self.str_to_date(element.start_date)
            enddate = self.str_to_date(element.expiration_date)
            diffdate = (enddate-startdate)
            newenddate = enddate+diffdate
            temp.append(('default_expiration_date',str(newenddate)))

            res['context'] = dict(temp)
            
        return res

    def _get_default_contract_type(self, cr, uid, context):
        try:
            model, model_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'fleet', 'type_contract_leasing')
        except ValueError:
            model_id = False
        return model_id

    _name = 'fleet.vehicle.log.contract'
    _order='state,expiration_date'
    _columns = {
        'name' : fields.function(_vehicle_contract_name_get_fnc, type="text", string='Name', store=True),

        'start_date' : fields.date('Contract Start Date', required=False, help='Date when the coverage of the contract begins'),
        'expiration_date' : fields.date('Contract Expiration Date', required=False, help='Date when the coverage of the contract expirates (by default, one year after begin date)'),
        'warning_date' : fields.function(get_warning_date,type='integer',string='Warning Date',store=False),

        'insurer_id' :fields.many2one('res.partner', 'Supplier', domain="[('supplier','=',True)]"),
        'purchaser_id' : fields.many2one('res.partner', 'Contractor',domain="['|',('customer','=',True),('employee','=',True)]",help='Person to which the contract is signed for'),
        'ins_ref' : fields.char('Contract Reference', size=64),
        'state' : fields.selection([('open', 'In Progress'), ('closed', 'Terminated')], 'Status', readonly=True, help='Choose wheter the contract is still valid or not'),
        #'reminder' : fields.boolean('Renewal Reminder', help="Warn the user a few days before the expiration date of this contract"),
        'notes' : fields.text('Terms and Conditions', help='Write here all supplementary informations relative to this contract'),
        'odometer_id' : fields.many2one('fleet.vehicle.odometer', 'Odometer', required=False, help='Odometer measure of the vehicle at the moment of this log'),
        'odometer' : fields.function(_get_odometer,fnct_inv=_set_odometer,type='char',string='Odometer Value',store=False,help='Odometer measure of the vehicle at the moment of this log'),
        'odometer_unit': fields.related('vehicle_id','odometer_unit',type="char",string="Unit",store=False, readonly=True),
        'cost_amount': fields.related('cost_id','amount',type="float",string="Amount",store=True, readonly=True),
        'cost_generated': fields.float('Recurring Cost Amount',help="Costs paid at regular intervals, depending on the cost frequency. If the cost frequency is set to unique, the cost will be logged at the start date"),
        'cost_frequency': fields.selection([('no','No'),('daily', 'Daily'),('weekly','Weekly'),('monthly','Monthly'),('yearly','Yearly')], 'Recurring Cost Frequency', help='Frequency of the recuring cost',required=True),
        'generated_cost_ids' : fields.one2many('fleet.vehicle.cost', 'contract_id', 'Generated Costs',ondelete='cascade'),
    }
    _defaults = {
        'purchaser_id': lambda self, cr, uid, ctx: uid,
        'date' : time.strftime('%Y-%m-%d'),
        'start_date' : time.strftime('%Y-%m-%d'),
        'state':'open',
        'expiration_date' : lambda self,cr,uid,ctx: self.compute_next_year_date(time.strftime('%Y-%m-%d')),
        'cost_frequency' : 'no',
        'cost_subtype' : _get_default_contract_type,
    }

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        current_object = self.browse(cr,uid,id,context)
        default['date'] = time.strftime('%Y-%m-%d')
        default['start_date'] = time.strftime('%Y-%m-%d')
        default['expiration_date'] = self.compute_next_year_date(time.strftime('%Y-%m-%d'))
        #default['name'] = current_object.name
        default['ins_ref'] = ''
        default['state'] = 'open'
        default['notes'] = ''
        default['date'] = time.strftime('%Y-%m-%d')

        #default['odometer'] = current_object.odometer
        #default['odometer_unit'] = current_object.odometer_unit
        return super(fleet_vehicle_log_contract, self).copy(cr, uid, id, default, context=context)

    def contract_close(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'closed'})
        return True

    def contract_open(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'open'})
        return True
    def create(self, cr, uid, data, context=None):
        data['cost_type'] = 'contract'
        cost_id = super(fleet_vehicle_log_contract, self).create(cr, uid, data, context=context)
        return cost_id


############################
############################
#Vehicle.log.contract.state class
############################
############################

class fleet_contract_state(osv.Model):
    _name = 'fleet.contract.state'
    _columns = {
        'name':fields.char('Contract Status',size=32),
    }