openerp.survey = function(openerp) {
    openerp.web_kanban.KanbanRecord.include({
        on_card_clicked: function(e) {
            if (this.view.dataset.model === 'survey') {
                if(!$(event.target).hasClass('oe_inactive')) {
                    this.$('.oe_kanban_survey_list .oe_survey_fill').first().click();
                }
            } else {
                this._super.apply(this, arguments);
            }
        },
    });
};
