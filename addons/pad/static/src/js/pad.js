openerp.pad = function(instance) {

instance.web.form.FieldEtherpad = instance.web.form.AbstractField.extend(_.extend({}, instance.web.form.ReinitializeFieldMixin, {
    template: 'FieldEtherpad',
    initialize_content: function() {
        this.$textarea = undefined;         
        this.$element.find('span').text(this.field.string);
        this.$element.find('span').click(_.bind(function(ev){
            this.$element.find('span').toggleClass('etherpad_zoom_head');
            var iszoom = this.$element.find('span').hasClass('etherpad_zoom_head');
            this.$element.find('span').text((iszoom?'Back to Task':this.field.string));
            this.$element.find('div').toggleClass('etherpad_zoom');
            $("body").toggleClass('etherpad_body');            
            },this));
            
        },
        set_value: function(value_) {
            this._super(value_);
            this.render_value();
        },
        render_value: function() {            
            var show_value = instance.web.format_value(this.get('value'), this, '');                        
            if (!this.get("effective_readonly")) {     
               // var pad_url = show_value.split('\n')[0];
//                var api_url = pad_url.substring( 0, (pad_url.search("/p/")+1) );
  //              var pad_id = pad_url.substring((pad_url.search("p/")+2) );
    //            console.log(this);
                this.$element.find('div').html('<iframe width="100%" height="100%" frameborder="0"  src="'+pad_url+'?showChat=false&showLineNumbers=false"></iframe>');
            
            } else {
                if(this.get('value') != false)
                {
                    var self = this;
                    if(show_value.split('\n')[0] != '')             
                        $.get(show_value.split('\n')[0]+'/export/html')
                        .success(function(data) { self.$element.html('<div class="etherpad_readonly">'+data+'</div>'); })
                        .error(function() { self.$element.text('Unable to load pad'); });
                }                    
            }
        },
        
        
    }));    
    
    instance.web.form.widgets = instance.web.form.widgets.extend({
        'etherpad': 'instance.web.form.FieldEtherpad',
    });
};  
