(function(){
    $.fn.share = function(options) {
        var option = $.extend($.fn.share.defaults,options);
        $.extend($.fn.share,{
            init : function(shareable) {
                $.fn.share.defaults.shareable = shareable;
            },
            getContent : function() {
                var current_url = window.location.href
                var selected_text = this.getSelection('string').substring(0,option.maxLength-(current_url.length+3));
                var text = encodeURIComponent('\"'+selected_text+'\" '+ current_url)
                return '<a href="'+option.shareLink+text+'"target=\"_'+option.target+'\""><i class="fa fa-twitter fa-lg"</a>';
            },
            getSelection : function(share) {
                if(window.getSelection){
                    return (share=='string')?String(window.getSelection().getRangeAt(0)).replace(/\s{2,}/g, ' '):window.getSelection().getRangeAt(0);
                }
                else if(document.selection){
                    return (share=='string')?document.selection.createRange().text.replace(/\s{2,}/g, ' '):document.selection.createRange();
                }
            },
            popOver : function() {
                if(this.getSelection('string').length < option.minLength)
                    return;
                var data = this.getContent();
                var range = this.getSelection();
                var newNode = document.createElement("mark");
                range.surroundContents(newNode);
                $('mark').addClass(option.className);
                $('.'+option.className).popover({trigger:'manual', placement: option.placement, html: true 
                , content:function(){
                        return data;
                    }
                });
                $('.'+option.className).popover('show');
            },
            destroy : function(){
                $('.'+option.className).popover('hide');
                $('mark').contents().unwrap();
                $('mark').remove();
            }
        });
        $.fn.share.init(this);
    };
    
    $.fn.share.defaults = {
        shareLink : "http://twitter.com/intent/tweet?text=",
        minLength  : 5,
        maxLength  : 140,
        target     : "blank",
        className  : "share",
        placement  : "top",
    };

}());

$(document).ready(function(){
    $("p").share();
    $.fn.share.defaults.shareable.on('mouseup',function(){
        $.fn.share.popOver();
    });
    $.fn.share.defaults.shareable.on('mousedown',function(){
        $.fn.share.destroy();
    });
});
