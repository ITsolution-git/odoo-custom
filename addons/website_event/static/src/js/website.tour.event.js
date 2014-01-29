(function () {
    'use strict';

    var website = openerp.website;

    website.EditorBar.include({
        start: function () {
            this.registerTour(new website.EventTour(this));
            return this._super();
        },
    });

    website.EventTour = website.Tour.extend({
        id: 'event',
        name: "Create an event",
        init: function (editor) {
            var self = this;
            self.steps = [
                {
                    stepId:    'welcome-event',
                    title:     "Create an Event",
                    content:   "Let's go through the first steps to publish a new event.",
                    template:  self.popover({ next: "Start Tutorial", end: "Skip It" }),
                    backdrop:  true,
                },
                {
                    stepId:    'content-menu',
                    element:   '#content-menu-button',
                    placement: 'left',
                    title:     "Add Content",
                    content:   "The <em>Content</em> menu allows you to create new pages, events, menus, etc.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'click',
                },
                {
                    stepId:    'new-post-entry',
                    element:   'a[data-action=new_event]',
                    placement: 'left',
                    title:     "New Event",
                    content:   "Click here to create a new event.",
                    template:  self.popover({ fixed: true }),
                    trigger: {
                        modal: {
                            stopOnClose: true,
                            afterSubmit: 'event-page',
                        },
                    },
                },
                {
                    stepId:    'choose-name',
                    element:   '.modal input',
                    sampleText: 'Advanced Technical Training',
                    placement: 'right',
                    title:     "Create an Event Name",
                    content:   "Create a name for your new event and click <em>'Continue'</em>. e.g: Technical Training",
                },
                {
                    stepId:    'continue-name',
                    element:   '.modal button.btn-primary',
                    placement: 'right',
                    title:     "Create Event",
                    content:   "Click <em>Continue</em> to create the event.",
                    trigger: {
                        url:        /event\/[0-9]+\/register/
                    },
                },
                {
                    stepId:    'event-page',
                    title:     "New Event Created",
                    content:   "This is your new event page. We will edit the event presentation page.",
                    template:  self.popover({ next: "OK" }),
                },
                {
                    stepId:    'add-banner',
                    element:   'button[data-action=snippet]',
                    placement: 'bottom',
                    title:     "Layout your event",
                    content:   "Insert blocks to layout the body of your event.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'click',
                },
                {
                    stepId:    'drag-banner',
                    snippet:   'image-text',
                    placement: 'bottom',
                    title:     "Drag & Drop a block",
                    content:   "Drag the 'Image-Text' block and drop it in your page.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'drag',
                },
                {
                    stepId:    'add-text-block',
                    element:   'button[data-action=snippet]',
                    placement: 'bottom',
                    title:     "Layout your event",
                    content:   "Insert another block to your event.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'click',
                },
                {
                    stepId:    'drag-text-block',
                    snippet:   'text-block',
                    placement: 'bottom',
                    title:     "Drag & Drop a block",
                    content:   "Drag the 'Text Block' in your event page.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'drag',
                },
                {
                    stepId:    'add-three-columns',
                    element:   'button[data-action=snippet]',
                    placement: 'bottom',
                    title:     "Layout your event",
                    content:   "Insert a last block to your event.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'click',
                },
                {
                    stepId:    'drag-three-columns',
                    snippet:   'three-columns',
                    placement: 'bottom',
                    title:     "Drag & Drop a block",
                    content:   "Drag the 'Three Columns' block at the bottom.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'drag',
                },
                {
                    stepId:    'save-changes',
                    element:   'button[data-action=save]',
                    placement: 'right',
                    title:     "Save your modifications",
                    content:   "Once you click on save, your event is updated.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'reload',
                },
                {
                    stepId:    'publish-event',
                    element:   'button.btn-danger.js_publish_btn',
                    placement: 'top',
                    title:     "Publish your event",
                    content:   "Click to publish your event.",
                    trigger:   'click',
                },
                {
                    stepId:    'customize-event',
                    element:   '.js_publish_management button[data-toggle="dropdown"]',
                    placement: 'left',
                    title:     "Customize your event",
                    content:   "Click here to customize your event further.",
                    trigger:   'click',
                },
                {
                    stepId:    'edit-event-backend',
                    element:   '.js_publish_management ul>li>a:last',
                    placement: 'left',
                    title:     "Customize your event",
                    content:   "Click here to edit your event in the backend.",
                    trigger:   'click',
                },
                {
                    stepId:    'end-tutorial',
                    title:     "Thanks!",
                    content:   "This tutorial is finished. Congratulations on creating your first event.",
                    template:  self.popover({ end: "Close Tutorial" }),
                    backdrop:  true,
                },
            ];
            return this._super();
        },
        trigger: function () {
            return (this.resume() && this.testUrl(/^\/event\/[0-9]+\/register/)) || this._super();
        },
    });

}());
