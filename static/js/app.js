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

    // Einheitliches Bestätigen-und-Löschen-Muster für alle Listen (Kategorien,
    // Verbindlichkeiten, Buchungen, Serien, Vermögensgegenstände, Aufgaben).
    // Ein Klick auf ein Element mit data-delete-url öffnet das globale
    // #confirmDeleteModal (siehe base.html); nach Bestätigung wird per fetch()
    // gelöscht, damit sowohl Erfolg (Status 2xx) als auch Fehler (z.B. 400 bei
    // "Kategorie hat noch Buchungen") einheitlich behandelt werden können –
    // reines htmx.ajax swappt bei 4xx/5xx standardmäßig nicht.
    //
    // Unterstützte data-Attribute am Trigger:
    //   data-delete-url            (Pflicht) Lösch-Endpunkt (POST)
    //   data-delete-title          Modal-Titel (Default: "Eintrag löschen")
    //   data-delete-message        Bestätigungstext
    //   data-delete-warning        zusätzlicher Hinweistext (alert-warning)
    //   data-delete-target         CSS-Selektor des Elements, das bei Erfolg
    //                              entfernt (outerHTML) oder geleert (innerHTML)
    //                              wird
    //   data-delete-swap           "outerHTML" (Default) oder "innerHTML"
    //   data-delete-reload-target  CSS-Selektor, der stattdessen per GET neu
    //                              geladen wird (z.B. Monatsansicht, wo Summen
    //                              neu berechnet werden müssen)
    //   data-delete-reload-url     URL für den Reload (Default: aktuelle Seite)
    //   data-delete-error-target   CSS-Selektor für die Fehleranzeige (Default:
    //                              #delete-error-container aus base.html)
    function initConfirmDelete() {
        var modalEl = document.getElementById('confirmDeleteModal');
        if (!modalEl) {
            return;
        }
        var modal = new bootstrap.Modal(modalEl);
        var titleEl = document.getElementById('confirmDeleteModalLabel');
        var messageEl = document.getElementById('confirmDeleteModalMessage');
        var warningEl = document.getElementById('confirmDeleteModalWarning');
        var confirmBtn = document.getElementById('confirmDeleteModalBtn');
        var pending = null;

        function showError(html, errorTargetSelector) {
            var container = (errorTargetSelector && document.querySelector(errorTargetSelector)) ||
                document.getElementById('delete-error-container');
            if (!container) {
                return;
            }
            container.innerHTML = html;
            container.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        document.body.addEventListener('click', function (event) {
            var trigger = event.target.closest('[data-delete-url]');
            if (!trigger) {
                return;
            }
            event.preventDefault();

            pending = {
                url: trigger.getAttribute('data-delete-url'),
                target: trigger.getAttribute('data-delete-target'),
                swap: trigger.getAttribute('data-delete-swap') || 'outerHTML',
                reloadTarget: trigger.getAttribute('data-delete-reload-target'),
                reloadUrl: trigger.getAttribute('data-delete-reload-url') || window.location.pathname,
                errorTarget: trigger.getAttribute('data-delete-error-target')
            };

            titleEl.textContent = trigger.getAttribute('data-delete-title') || 'Eintrag löschen';
            messageEl.textContent = trigger.getAttribute('data-delete-message') ||
                'Sind Sie sicher, dass Sie diesen Eintrag löschen möchten?';

            var warning = trigger.getAttribute('data-delete-warning');
            if (warning) {
                warningEl.textContent = warning;
                warningEl.classList.remove('d-none');
            } else {
                warningEl.classList.add('d-none');
            }

            modal.show();
        });

        confirmBtn.addEventListener('click', function () {
            if (!pending) {
                return;
            }
            var current = pending;
            pending = null;
            modal.hide();

            fetch(current.url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content'),
                    'HX-Request': 'true'
                }
            }).then(function (response) {
                if (!response.ok) {
                    return response.text().then(function (text) {
                        showError(text, current.errorTarget);
                    });
                }

                if (current.reloadTarget) {
                    return htmx.ajax('GET', current.reloadUrl, {
                        target: current.reloadTarget,
                        swap: 'innerHTML'
                    });
                }

                if (current.target) {
                    var el = document.querySelector(current.target);
                    if (el) {
                        if (current.swap === 'innerHTML') {
                            el.innerHTML = '';
                        } else {
                            el.remove();
                        }
                    }
                }
            }).catch(function () {
                showError('<div class="alert alert-danger">Ein Fehler ist aufgetreten.</div>', current.errorTarget);
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initTooltips(document);
        initPopovers(document);
        initMobileNavAutoClose();
        openQuickAction();
        initConfirmDelete();
    });

    // HTMX tauscht Teile des DOM aus – Bootstrap-Komponenten in neu
    // eingefügtem Markup müssen danach erneut initialisiert werden.
    document.body.addEventListener('htmx:afterSwap', function (event) {
        initTooltips(event.target);
        initPopovers(event.target);
    });
})();
