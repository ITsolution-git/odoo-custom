(function () {
    'use strict';

    var website = openerp.website;

    website.EditorBar.include({
        start: function () {
            this.registerTour(new website.BlogTour(this));
            return this._super();
        },
    });

    website.BlogTour = website.Tour.extend({
        id: 'blog',
        name: "Create a blog post",
        init: function (editor) {
            var self = this;
            self.steps = [
                {
                    stepId:    'welcome-blog',
                    title:     "New Blog Post",
                    content:   "Let's go through the first steps to write beautiful blog posts.",
                    template:  self.popover({ next: "Start Tutorial", end: "Skip" }),
                    backdrop:  true,
                },
                {
                    stepId:    'content-menu',
                    element:   '#content-menu-button',
                    placement: 'left',
                    title:     "Add Content",
                    content:   "Create new pages, blogs, menu items and products through the <em>'Content'</em> menu.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'click',
                },
                {
                    stepId:    'new-post-entry',
                    element:   'a[data-action=new_blog_post]',
                    placement: 'left',
                    title:     "New Blog Post",
                    content:   "Select this entry to create a new blog post.",
                    template:  self.popover({ fixed: true }),
                    trigger: {
                        modal: {
                            stopOnClose: true,
                            afterSubmit: 'post-page',
                        },
                    },
                },
                {
                    stepId:    'choose-category',
                    element:   '.modal select',
                    placement: 'right',
                    title:     "Which Blog?",
                    content:   "Blog posts are organized in multiple categories (news, job offers, events, etc). Select <em>News</em> and click <em>Continue</em>.",
                    trigger: {
                        id: 'change',
                    },
                },
                {
                    stepId:    'continue-category',
                    element:   '.modal button.btn-primary',
                    placement: 'right',
                    title:     "Create Blog Post",
                    content:   "Click <em>Continue</em> to create the blog post.",
                    trigger:   'click',
                },
                {
                    stepId:    'post-page',
                    title:     "Blog Post Created",
                    content:   "This is your new blog post. We will edit your pages inline. What You See Is What You Get. No need for a complex backend.",
                    template:  self.popover({ next: "Continue" }),
                },
                {
                    stepId:    'post-title',
                    element:   'h1[data-oe-expression="blog_post.name"]',
                    placement: 'top',
                    title:     "Pick a Title",
                    content:   "Click on this area and set a catchy title.",
                    template:  self.popover({ next: "OK" }),
                },
                {
                    stepId:    'add-image-text',
                    element:   'button[data-action=snippet]',
                    placement: 'bottom',
                    title:     "Layout Your Blog Post",
                    content:   "Use well designed building blocks to structure the content of your blog. Click 'Insert Blocks' to add new content.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'click',
                },
                {
                    stepId:    'drag-image-text',
                    snippet:   'image-text',
                    placement: 'bottom',
                    title:     "Drag & Drop a Block",
                    content:   "Drag the <em>'Image-Text'</em> block and drop it in your page.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'drag',
                },
                {
                    stepId:    'add-text-block',
                    element:   'button[data-action=snippet]',
                    placement: 'bottom',
                    title:     "Add Another Block",
                    content:   "Let's add another block to your post.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'click',
                },
                {
                    stepId:    'drag-text-block',
                    snippet:   'text-block',
                    placement: 'bottom',
                    title:     "Drag & Drop a block",
                    content:   "Drag the <em>'Text Block'</em> block and drop it below the image block.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'drag',
                },
                {
                    stepId:    'activate-text-block-title',
                    element:   '#wrap [data-snippet-id=text-block] .text-center[data-snippet-id=colmd]',
                    placement: 'top',
                    title:     "Edit an Area",
                    content:   "Select any area of the page to modify it. Click on this subtitle.",
                    trigger: {
                        id: 'snippet-activated',
                    }
                },
                {
                    stepId:    'remove-text-block-title',
                    element:   '.oe_active .oe_snippet_remove',
                    placement: 'top',
                    title:     "Delete the Title",
                    content:   "From this toolbar you can move, duplicate or delete the selected zone. Click on the cross to delete the title.",
                    trigger:   'click',
                },
                {
                    stepId:    'save-changes',
                    element:   'button[data-action=save]',
                    placement: 'right',
                    title:     "Save Your Blog",
                    content:   "Click the <em>Save</em> button to record changes on the page.",
                    template:  self.popover({ fixed: true }),
                    trigger:   'click',
                },
                {
                    stepId:    'publish-post',
                    element:   'button.btn-danger.js_publish_btn',
                    placement: 'top',
                    title:     "Publish Your Post",
                    content:   "Your blog post is not yet published. You can update this draft version and publish it once you are ready.",
                    trigger:   'click',
                },
                {
                    stepId:    'end-tutorial',
                    title:     "Thanks!",
                    content:   "This tutorial is finished. To discover more features, improve the content of this page and try the <em>Promote</em> button in the top right menu.",
                    template:  self.popover({ end: "Close Tutorial" }),
                    backdrop:  true,
                },
            ];
            return this._super();
        },
        trigger: function () {
            return (this.resume() && this.testUrl(/^\/blogpost\/[0-9]+\//)) || this._super();
        },
    });

}());
