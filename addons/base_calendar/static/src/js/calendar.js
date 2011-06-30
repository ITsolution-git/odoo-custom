/*---------------------------------------------------------
 * OpenERP base_calendar
 *---------------------------------------------------------*/

openerp.base_calendar = function(openerp) {
QWeb.add_template('/base_calendar/static/src/xml/base_calendar.xml');
openerp.base.views.add('calendar', 'openerp.base_calendar.CalendarView');
openerp.base_calendar.CalendarView = openerp.base.Controller.extend({
// Dhtmlx scheduler ?
	init: function(view_manager, session, element_id, dataset, view_id){
		this._super(session, element_id);
		this.view_manager = view_manager;
        this.dataset = dataset;
        this.model = dataset.model;
        this.view_id = view_id;
        this.domain = this.dataset.domain || [];
		this.context = this.dataset.context || {};
	},
	start: function() {
		this.rpc("/base_calendar/calendarview/load", {"model": this.model, "view_id": this.view_id}, this.on_loaded);
	},
    on_loaded: function(data) {
		this.calendar_fields = {};
		this.ids = this.dataset.ids;
		this.day_lenth = 8;
		this.color_values = [];
		this.info_fields = [];
		
        this.fields_view = data.fields_view;
        this.name = this.fields_view.name || this.fields_view.arch.attrs.string;
		this.view_id = this.fields_view.view_id;
        
        this.date_start = this.fields_view.arch.attrs.date_start;
		this.date_delay = this.fields_view.arch.attrs.date_delay;
		this.date_stop = this.fields_view.arch.attrs.date_stop;
        
        this.colors = this.fields_view.arch.attrs.colors;
		this.day_length = this.fields_view.arch.attrs.day_length || 8;
		this.color_field = this.fields_view.arch.attrs.color;
		this.fields =  this.fields_view.fields;
        
        //* Calendar Fields *
		this.calendar_fields['date_start'] = {'name': this.date_start, 'kind': this.fields[this.date_start]['type']};
		
		if(this.date_delay)
			this.calendar_fields['date_delay'] = {'name': this.date_delay, 'kind': this.fields[this.date_delay]['type']};
			
		if(this.date_stop)
			this.calendar_fields['date_stop'] = {'name': this.date_stop, 'kind': this.fields[this.date_stop]['type']};
		
		//* ------- *
        
        for(var fld=0;fld<this.fields_view.arch.children.length;fld++) {
			this.info_fields.push(this.fields_view.arch.children[fld].attrs.name);
		}
      
        this.load_scheduler();
    },
	
    load_scheduler: function() {
        var self = this;
        this.dataset.read_slice([], 0, false, function(events) {
            if (self.session.locale_code) {
                $LAB.setOptions({AlwaysPreserveOrder: true})
                .script([
                    '/base_calendar/static/lib/dhtmlxScheduler/sources/locale_'+self.session.locale_code+'.js',
                    '/base_calendar/static/lib/dhtmlxScheduler/sources/locale_recurring_'+self.session.locale_code+'.js'
                ])
                .wait(function() {
                    self.schedule_events(events);        
                });
                
            } else {
                self.schedule_events(events);
            }
        });
    },
    
    schedule_events: function(events) {
        this.$element.html(QWeb.render("CalendarView", {"fields_view": this.fields_view}));
        /*
		 * Initialize dhtmlx Schedular
		 */
        
        scheduler.clearAll();
        scheduler.config.api_date="%Y-%m-%d %H:%M:%S";
        scheduler.config.details_on_dblclick=true;
        scheduler.config.details_on_create = true;
		
        if(this.fields[this.date_start]['type'] == 'time') {
            scheduler.config.xml_date="%H:%M:%S";
        } else {
            scheduler.config.xml_date="%Y-%m-%d %H:%M:%S";
            
        }
        
        this.mode = this.mode || 'month';
        
        scheduler.config.multi_day = true; //Multi day events are not rendered in daily and weekly views
        
        // Initialize Sceduler
		scheduler.init('openerp_scheduler',null,this.mode);
        
        //To parse Events we have to convert date Format
        var res_events = [];
        for(var e=0;e<events.length;e++) {
            var evt = events[e];
            if(!evt[this.date_start]) {
                this.notification.warn("Start date is not defined for event :", evt['id']);
                break;
            }
            
            if (this.fields[this.date_start]['type'] == 'date') {
                evt[this.date_start] = openerp.base.parse_date(evt[this.date_start]).set({hour: 9}).toString('yyyy-MM-dd HH:mm:ss')
            }
            if(this.date_stop && evt[this.date_stop] && this.fields[this.date_stop]['type'] == 'date') {
                evt[this.date_stop] = openerp.base.parse_date(evt[this.date_stop]).set({hour: 17}).toString('yyyy-MM-dd HH:mm:ss')
            }
            res_events.push(this.convert_event(evt))
        }
        
        scheduler.parse(res_events,"json");
        jQuery('#dhx_minical_icon').bind('click', this.mini_calendar);
        
        // Event Options Click,edit
        var self = this;
        scheduler.attachEvent(
            "onDblClick",
            function(event_id, e) {
                self.popup_event(event_id);
                e.stopPropagation();
                e.preventDefault();
            }
        );
        
        scheduler.attachEvent(
            "onEventCreated",
            function(event_id, e) {
                //Replace default Lightbox with Popup Form of new Event
            	
                scheduler.showLightbox = function(){
                    //Delete Newly created Event,Later we reload Scheduler
                    scheduler.deleteEvent(event_id)
                    self.popup_event();
                    e.stopPropagation();
                    e.preventDefault();
                }
            }
        );
        
        scheduler.attachEvent("onBeforeEventChanged", function(event_obj, native_event, is_new) {
        	var is_event_exist = jQuery.inArray(event_obj.id, self.dataset.ids);
        	if(is_event_exist >= 0 || !is_new) {
        		// try to save Event.
        		var data = {};
        		self.mode = scheduler._mode;
        		var date_format = self.calendar_fields.date_start.kind == 'time' ? 'HH:mm:ss' : 'yyyy-MM-dd HH:mm:ss';
        		data[self.date_start] = event_obj.start_date.toString(date_format);
        		
        		if(self.date_stop) {
        			data[self.date_stop] = event_obj.end_date.toString(date_format);
        		}
        		
        		if(self.date_delay) {
        			var tds = (event_obj.start_date.getOrdinalNumber() / 1e3 >> 0) - (event_obj.start_date.getOrdinalNumber() < 0);
        			var tde = (event_obj.end_date.getOrdinalNumber() / 1e3 >> 0) - (event_obj.end_date.getOrdinalNumber() < 0);
        			var n = (tde - tds) / (60 * 60);
        			if(n > self.day_length) {
                    	var d = Math.floor(n / 24),
                        	h = n % 24;
                    	
                    	n = d * self.day_length + h;
                    }
        			data[self.date_delay] = n;
        		}
        		
        		self.dataset.write(event_obj.id, data, function(){self.load_scheduler()});
        	} else {
        		// new Event.
        		return true;
        	}
        });
    },
    
    convert_event: function(event) {
    	var starts = event[this.date_start],
    		ends = event[this.date_delay] || 1,
    		span = 0,
    		res_text = '',
    		res_description = [];
    	
    	var parse_start_date = openerp.base.parse_datetime(starts);
    	if(event[this.date_stop]) {
    		var parse_end_date = openerp.base.parse_datetime(event[this.date_stop]);
    	}
       if(this.info_fields) {
    	   var fld = event[this.info_fields[0]];
    	   
           if(typeof fld == 'object') res_text = fld[fld.length -1];
           else res_text = fld;
           
           var sliced_info_fields = this.info_fields.slice(1);
           for(sl_fld in sliced_info_fields) {
               var slc_fld = event[sliced_info_fields[sl_fld]];
               
               if(typeof slc_fld == 'object') res_description.push(slc_fld[slc_fld.length - 1]);  
               else {
                   if(slc_fld) res_description.push(slc_fld);
               }
           }
       }
       
       if(starts && ends) {
    		var n = 0,
    			h = ends;
    		if(ends == this.day_length) span = 1;
    		else if(ends > this.day_length) {
    			n = ends / this.day_length,
    			h = ends % this.day_length
    			n = parseInt(Math.floor(n));
    			
    			if(h > 0) span = n + 1;
    			else span = n;
    		}
    		var start = parse_start_date.setTime((parse_start_date.getTime() + (h * 60 * 60) + (n * 24 * 60 * 60)))
    		ends = parse_start_date;
    	}
    	
    	if(starts && this.date_stop) {
    		ends = parse_end_date;
    		if(event[this.date_stop] == undefined) {
        		var start = parse_start_date.setTime((parse_start_date.getTime() + (h * 60 * 60) + (n * 24 * 60 * 60)))
    			ends = parse_start_date;
    		}
    		var tds = parse_start_date.getTime(),
    			tde = parse_end_date.getTime();
    		
    		if(tds >= tde) {
    			tde = tds + 60 * 60;
    			parse_end_date.setTime(tde);
    			ends = parse_end_date;
    		}
    		n = (tde - tds) / (60 * 60);
    		
    		if (n >= this.day_length) span = Math.ceil(n / 24);
    	}
    	
    	return {
            'start_date': parse_start_date.toString('yyyy-MM-dd HH:mm:ss'),
            'end_date': ends.toString('yyyy-MM-dd HH:mm:ss'),
            'text': res_text,
            'id': event['id'],
            'title': res_description.join()
            }
    },
    
    
    mini_calendar: function() {
		
		if(scheduler.isCalendarVisible()) {
			scheduler.destroyCalendar();
		} else {
			scheduler.renderCalendar({
				position:"dhx_minical_icon",
            	date:scheduler._date,
            	navigation:true,
				handler:function(date,calendar){
	               scheduler.setCurrentView(date);
	               scheduler.destroyCalendar()
	            }
			});
		}
	},
    
    do_search: function(domains, contexts, groupbys) {
        var self = this;
        this.rpc('/base/session/eval_domain_and_context', {
            domains: domains,
            contexts: contexts,
            group_by_seq: groupbys
        }, function (results) {
            // TODO: handle non-empty results.group_by with read_group
            self.dataset.context = self.context = results.context;
            self.dataset.domain = self.domain = results.domain;
            self.dataset.read_slice(self.fields, 0, self.limit,function(events){
                self.schedule_events(events)
            });
        });
    },
	
	do_show: function () {
        this.$element.show();
    },
	
    do_hide: function () {
        this.$element.hide();
    },
    
    popup_event: function(event_id) {
        
    	var self = this;
    	if(event_id) event_id = parseInt(event_id, 10);
    	
        var action = {
    		"res_model": this.dataset.model,
    		"res_id": event_id,
            "views":[[false,"form"]],
            "type":"ir.actions.act_window",
            "view_type":"form",
            "view_mode":"form"
        }
        
        action.flags = {
    		search_view: false,
            sidebar : false,
            views_switcher : false,
            action_buttons : false,
            pager: false
            }
        var element_id = _.uniqueId("act_window_dialog");
        
        var dialog = jQuery('<div>', {
            'id': element_id
            }).dialog({
                modal: true,
                width: 'auto',
                height: 'auto',
                buttons: {
            		Cancel: function() {
            			$(this).dialog("destroy");
            		},
            		Save: function() {
            			var view_manager = action_manager.viewmanager;
            			var _dialog = this;
            			view_manager.views[view_manager.active_view].controller.do_save(function(r) {
            				$(_dialog).dialog("destroy");
//            				self.start();
            				self.load_scheduler();
            			})
            		}
            	}
        });
        var action_manager = new openerp.base.ActionManager(this.session, element_id);
        action_manager.start();
        action_manager.do_action(action);
        
        //Default_get
        if(!event_id) action_manager.viewmanager.dataset.index = null;
    }
});

};

// DEBUG_RPC:rpc.request:('execute', 'addons-dsh-l10n_us', 1, '*', ('ir.filters', 'get_filters', u'res.partner'))
// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
