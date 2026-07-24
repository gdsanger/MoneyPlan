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

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function showGlobalAlert(html) {
        var container = document.getElementById('global-alert-container');
        if (!container) {
            return;
        }
        container.innerHTML = html;
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function clearGlobalAlert() {
        var container = document.getElementById('global-alert-container');
        if (container) {
            container.innerHTML = '';
        }
    }

    // Einheitliches Bestätigen-und-Löschen-Muster für Kategorien, Verbindlichkeiten
    // und Buchungen: ein Trigger-Element trägt data-delete-* Attribute, der Rest
    // (Modal, Request, Fehleranzeige, Entfernen/Neuladen) läuft zentral hier.
    //
    // Unterstützte Attribute auf dem Trigger:
    //   data-delete-confirm        Marker, aktiviert das Muster für dieses Element
    //   data-delete-url            Ziel-URL des Lösch-POST (required)
    //   data-delete-title          Modal-Titel (optional)
    //   data-delete-message        Bestätigungstext (optional)
    //   data-delete-warning        Zusätzlicher Warnhinweis im Modal (optional)
    //   data-delete-reload-target  CSS-Selektor eines Containers, der per HTMX-GET
    //                              neu geladen wird statt die Zeile zu entfernen
    //   data-delete-reload-full    "true" -> kompletter Seiten-Reload nach Erfolg
    // Ohne reload-Attribute wird die nächste <tr> des Triggers entfernt.
    function initDeleteConfirm() {
        var modalEl = document.getElementById('globalDeleteModal');
        if (!modalEl) {
            return;
        }
        var modal = new bootstrap.Modal(modalEl);
        var titleEl = document.getElementById('globalDeleteModalLabel');
        var messageEl = document.getElementById('globalDeleteModalMessage');
        var warningEl = document.getElementById('globalDeleteModalWarning');
        var warningTextEl = document.getElementById('globalDeleteModalWarningText');
        var confirmBtn = document.getElementById('globalDeleteConfirmBtn');
        var pendingTrigger = null;

        document.body.addEventListener('click', function (event) {
            var trigger = event.target.closest('[data-delete-confirm]');
            if (!trigger) {
                return;
            }
            event.preventDefault();
            pendingTrigger = trigger;

            titleEl.textContent = trigger.getAttribute('data-delete-title') || 'Eintrag löschen';
            messageEl.textContent = trigger.getAttribute('data-delete-message') ||
                'Sind Sie sicher, dass Sie diesen Eintrag löschen möchten?';

            var warningText = trigger.getAttribute('data-delete-warning');
            if (warningText) {
                warningTextEl.textContent = warningText;
                warningEl.classList.remove('d-none');
            } else {
                warningEl.classList.add('d-none');
            }

            modal.show();
        });

        confirmBtn.addEventListener('click', function () {
            if (!pendingTrigger) {
                return;
            }
            var trigger = pendingTrigger;
            pendingTrigger = null;
            modal.hide();
            clearGlobalAlert();

            var url = trigger.getAttribute('data-delete-url');
            var row = trigger.closest('tr');
            var reloadTarget = trigger.getAttribute('data-delete-reload-target');
            var reloadFull = trigger.getAttribute('data-delete-reload-full') === 'true';

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'HX-Request': 'true'
                }
            }).then(function (response) {
                if (response.ok) {
                    if (reloadFull) {
                        window.location.reload();
                    } else if (reloadTarget) {
                        htmx.ajax('GET', window.location.pathname + window.location.search, {
                            target: reloadTarget,
                            swap: 'innerHTML'
                        });
                    } else if (row) {
                        row.remove();
                    }
                    return;
                }
                return response.text().then(function (html) {
                    showGlobalAlert(html && html.trim()
                        ? html
                        : '<div class="alert alert-danger">Löschen fehlgeschlagen.</div>');
                });
            }).catch(function () {
                showGlobalAlert('<div class="alert alert-danger">Ein Fehler ist aufgetreten.</div>');
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initTooltips(document);
        initPopovers(document);
        initDeleteConfirm();
    });

    // HTMX tauscht Teile des DOM aus – Bootstrap-Komponenten in neu
    // eingefügtem Markup müssen danach erneut initialisiert werden.
    document.body.addEventListener('htmx:afterSwap', function (event) {
        initTooltips(event.target);
        initPopovers(event.target);
    });
})();
