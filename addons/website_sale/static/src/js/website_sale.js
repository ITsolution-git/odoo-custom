$(document).ready(function () {
    var $shippingDifferent = $(".oe_website_sale input[name='shipping_different']");
    if ($shippingDifferent.is(':checked')) {
       $(".oe_website_sale .js_shipping").show();
    }
    $shippingDifferent.change(function () {
        $(".oe_website_sale .js_shipping").toggle();
    });

    // change for css
    $(document).on('mouseup', '.js_publish', function (ev) {
        $(ev.currentTarget).parents(".thumbnail").toggleClass("disabled");
    });

    $(".oe_website_sale .oe_cart input.js_quantity").change(function () {
        var $input = $(this);
        var value = parseInt($input.val(), 10);
        if (isNaN(value)) value = 0;
        openerp.jsonRpc("/shop/cart/update_json", 'call', {
            'line_id': parseInt($input.data('line-id'),10),
            'product_id': parseInt($input.data('product-id'),10),
            'set_qty': value})
            .then(function (data) {
                if (!data.quantity) {
                    location.reload();
                    return;
                }
                var $q = $(".my_cart_quantity");
                $q.parent().parent().removeClass("hidden", !data.quantity);
                $q.html(data.cart_quantity).hide().fadeIn(600);
                $input.val(data.quantity);
                $("#cart_total").replaceWith(data['website_sale.total']);
            });
    });

    // hack to add and rome from cart with json
    $('.oe_website_sale a.js_add_cart_json').on('click', function (ev) {
        ev.preventDefault();
        var $link = $(ev.currentTarget);
        var $input = $link.parent().parent().find("input");
        var quantity = ($link.has(".fa-minus").length ? -1 : 1) + parseFloat($input.val(),10);
        $input.val(quantity > 0 ? quantity : 0);
        $input.change();
        return false;
    });

    $('.a-submit').on('click', function () {
        $(this).closest('form').submit();
    });
    $('form.js_attributes input, form.js_attributes select').on('change', function () {
        $(this).closest("form").submit();
    });

    // change price when they are variants
    $('form.js_add_cart_json label').on('mouseup', function (ev) {
        var $label = $(this);
        var $price = $label.parents("form:first").find(".oe_price .oe_currency_value");
        if (!$price.data("price")) {
            $price.data("price", parseFloat($price.text()));
        }
        var value = $price.data("price") + parseFloat($label.find(".badge span").text() || 0);
        var dec = value % 1;
        $price.html(value + (dec < 0.01 ? ".00" : (dec < 1 ? "0" : "") ));
    });
    // hightlight selected color
    $('.css_attribute_color input').on('change', function (ev) {
        $('.css_attribute_color').removeClass("active");
        $('.css_attribute_color:has(input:checked)').addClass("active");
    });

    $('input.js_variant_change, select.js_variant_change').change(function (ev) {
        var $ul = $(this).parents('ul.js_add_cart_variants:first');
        var $parent = $ul.parents('.js_product:first');
        var $porduct_id = $parent.find('input.product_id, input.optional_product_id').first();
        var $price = $parent.find(".oe_price .oe_currency_value:first");
        var variant_ids = $ul.data("attribute_value_ids");
        var values = [];
        $parent.find('input.js_variant_change:checked, select.js_variant_change').each(function () {
            values.push(+$(this).val());
        });

        $parent.find("label").removeClass("text-muted css_not_available");

        var product_id = false;
        for (var k in variant_ids) {
            if (_.isEqual(variant_ids[k][1], values)) {
                var dec = ((variant_ids[k][2] % 1) * 100) | 0;
                $price.html(variant_ids[k][2] + (dec ? '' : '.0') + (dec%10 ? '' : '0'));
                product_id = variant_ids[k][0];
                break;
            }
        }

        $parent.find("input.js_variant_change:radio, select.js_variant_change").each(function () {
            var $input = $(this);
            var id = +$input.val();
            var values = [id];

            $parent.find("ul:not(:has(input.js_variant_change[value='" + id + "'])) input.js_variant_change:checked, select").each(function () {
                values.push(+$(this).val());
            });

            for (var k in variant_ids) {
                if (!_.difference(values, variant_ids[k][1]).length) {
                    return;
                }
            }
            $input.parents("label:first").addClass("css_not_available");
            $input.find("option[value='" + id + "']").addClass("css_not_available");
        });

        if (product_id) {
            $parent.removeClass("css_not_available");
            $porduct_id.val(product_id);
            $parent.find(".js_check_product").removeAttr("disabled");
        } else {
            $parent.addClass("css_not_available");
            $porduct_id.val(0);
            $parent.find(".js_check_product").attr("disabled", "disabled");
        }
    });
    $('ul.js_add_cart_variants').each(function () {
        $('input.js_variant_change, select.js_variant_change', this).first().trigger('change');
    });

    $('#product_detail form[action^="/shop/cart/update"] .a-submit').off("click").click(function (event) {
        event.preventDefault();
        var $link = $(this);
        var $form = $link.parents("form:first");
        var defs = [];
        $link.attr('disabled', 'disabled');
        $('.js_product', $form).each(function () {
            var product_id = parseInt($('input.optional_product_id', this).val(),10);
            var quantity = parseInt($('input.js_quantity', this).val(),10);
            if (product_id && quantity) {
                defs.push(openerp.jsonRpc("/shop/cart/update_json", 'call', {
                    'line_id': null,
                    'product_id': product_id,
                    'add_qty': quantity,
                    'display': false}));
            }
        });
        $.when.apply($.when, defs).then(function () {
            $form.submit();
        });
        return false;
    });

});
