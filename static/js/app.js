/*
 * MoneyPlan – globales UI-JavaScript
 *
 * Sammelt HTMX-Helfer sowie Init-Code für Bootstrap-Komponenten (Tooltips,
 * Popovers), damit einzelne Templates kein eigenes Inline-<script> dafür
 * brauchen. Wird nach Bootstrap- und HTMX-JS eingebunden.
 */
(function () {
    'use strict';

    function initTooltips(root) {
        root.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
            if (!bootstrap.Tooltip.getInstance(el)) {
                new bootstrap.Tooltip(el);
            }
        });
    }

    function initPopovers(root) {
        root.querySelectorAll('[data-bs-toggle="popover"]').forEach(function (el) {
            if (!bootstrap.Popover.getInstance(el)) {
                new bootstrap.Popover(el);
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initTooltips(document);
        initPopovers(document);
    });

    // HTMX tauscht Teile des DOM aus – Bootstrap-Komponenten in neu
    // eingefügtem Markup müssen danach erneut initialisiert werden.
    document.body.addEventListener('htmx:afterSwap', function (event) {
        initTooltips(event.target);
        initPopovers(event.target);
    });
})();
