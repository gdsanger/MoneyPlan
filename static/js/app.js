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

    // Schließt das mobile Offcanvas-Menü, sobald ein Link darin angeklickt wird
    // (Bootstrap tut das nicht von selbst, anders als beim klassischen Collapse-Menü).
    function initMobileNavAutoClose() {
        var offcanvasEl = document.getElementById('mobileNav');
        if (!offcanvasEl) {
            return;
        }
        offcanvasEl.querySelectorAll('.nav-link').forEach(function (link) {
            link.addEventListener('click', function () {
                var instance = bootstrap.Offcanvas.getInstance(offcanvasEl);
                if (instance) {
                    instance.hide();
                }
            });
        });
    }

    // Der mobile Schnellzugriff (FAB/Bottom-Bar) verlinkt auf die Buchungsliste
    // mit ?quickaction=..., damit von jeder Seite aus direkt das passende Modal
    // aufgeht, statt eine eigene Zielseite pro Aktion pflegen zu müssen.
    function openQuickAction() {
        var params = new URLSearchParams(window.location.search);
        var action = params.get('quickaction');
        if (!action) {
            return;
        }

        var triggerId = action === 'receipt' ? 'quickReceiptBtn' : action === 'create' ? 'quickNewBookingBtn' : null;
        var trigger = triggerId ? document.getElementById(triggerId) : null;
        if (trigger) {
            trigger.click();
        }

        params.delete('quickaction');
        var query = params.toString();
        var cleanUrl = window.location.pathname + (query ? '?' + query : '') + window.location.hash;
        window.history.replaceState({}, '', cleanUrl);
    }

    document.addEventListener('DOMContentLoaded', function () {
        initTooltips(document);
        initPopovers(document);
        initMobileNavAutoClose();
        openQuickAction();
    });

    // HTMX tauscht Teile des DOM aus – Bootstrap-Komponenten in neu
    // eingefügtem Markup müssen danach erneut initialisiert werden.
    document.body.addEventListener('htmx:afterSwap', function (event) {
        initTooltips(event.target);
        initPopovers(event.target);
    });
})();
