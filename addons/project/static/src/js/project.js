openerp.project = function(openerp) {
    openerp.web_kanban.ProjectKanban = openerp.web_kanban.KanbanRecord.include({
        bind_events: function() {
            self = this;
            self._super();
            if(this.view.dataset.model == 'project.project') {
                                
                /*set avatar title for members.
                In many2many fields, returns only list of ids.
                we can implement return value of m2m fields like [(1,"Adminstration"),...].
                */
                _.each($(this.$element).find('.project_avatar'),function(avatar){
                    var dataset = new openerp.web.DataSetSearch(this, 'res.users', self.session.context, [['id','=',avatar.id]]);
                    dataset.read_slice(['name']).then(function(result){
                    avatar.setAttribute("title",result[0].name)
                    });
                 });
                
                //if task is true , then open the task when click on the anywhere in the box.
                if(this.record.task.raw_value)$(this.$element).find('.click_button').attr('data-name','open_tasks');
                if(!this.record.task.raw_value)$(this.$element).find('.click_button').attr('data-name','dummy');
                
                // set sequence like Tasks,Issues,Timesheets and Phases
                my_list = $("#list a")
                my_list.sort(function (a, b) {
                    var aValue = parseInt(a.id);
                    var bValue = parseInt(b.id);
                    return aValue == bValue ? 0 : aValue < bValue ? -1 : 1;
                  });
                $('#list').replaceWith(my_list);
                
                /* set background color.
                  we can do other way to implement new widget.
                */
                this.$element.find('.bgcolor').click(function(){
                    color = parseInt($(this).find('span').attr('class').split(' ')[0].substring(16))
                    color_class = $(this).find('span').attr('class').split(' ')[0]
                    $(this).closest('#oe_project_kanban_vignette').removeClass().addClass(color_class + ' oe_project_kanban_vignette');
                    self.view.dataset.write(parseInt(this.id), {color:color});
                });
            };
        }
    });
}
