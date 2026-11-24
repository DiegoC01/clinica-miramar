(function () {
  document.documentElement.classList.add("js-ready");

  // 1. Navbar scroll state
  var header = document.getElementById("site-header");
  if (header) {
    var onScroll = function () {
      header.setAttribute("data-scrolled", window.scrollY > 12 ? "true" : "false");
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // 2. Menú móvil accesible
  var menuBtn = document.getElementById("mobile-menu-btn");
  var mobileMenu = document.getElementById("mobile-menu");
  var iconOpen = document.getElementById("menu-icon-open");
  var iconClose = document.getElementById("menu-icon-close");
  if (menuBtn && mobileMenu) {
    var setMenuOpen = function (open) {
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
      mobileMenu.classList.toggle("hidden", !open);
      if (iconOpen) iconOpen.classList.toggle("hidden", open);
      if (iconClose) iconClose.classList.toggle("hidden", !open);
    };
    menuBtn.addEventListener("click", function () {
      setMenuOpen(mobileMenu.classList.contains("hidden"));
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !mobileMenu.classList.contains("hidden")) {
        setMenuOpen(false);
        menuBtn.focus();
      }
    });
  }

  // 3. Animaciones de entrada suaves con IntersectionObserver
  var revealNodes = document.querySelectorAll("[data-reveal]");
  if (revealNodes.length > 0 && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -24px 0px" }
    );
    revealNodes.forEach(function (node) {
      io.observe(node);
    });
  } else {
    revealNodes.forEach(function (node) {
      node.classList.add("is-visible");
    });
  }

  // 4. Botones de cierre en alertas/toasts
  document.querySelectorAll("[data-dismiss-alert]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var box = btn.closest("[data-alert-box]");
      if (box) box.remove();
    });
  });

  // 5. Filtro combinado por categoría + texto en /paciente/resultados
  var examFilter = document.getElementById("exam-filter");
  var catButtons = document.querySelectorAll("[data-result-cat]");
  if (examFilter || catButtons.length > 0) {
    var rows = Array.prototype.slice.call(document.querySelectorAll(".exam-row"));
    var emptyRow = document.getElementById("exam-empty-row");
    var counter = document.getElementById("exam-visible-count");
    var activeCat = "todos";

    var applyResultFilters = function () {
      var term = examFilter ? examFilter.value.trim().toLowerCase() : "";
      var visible = 0;
      rows.forEach(function (row) {
        var hay = row.getAttribute("data-search") || "";
        var rtype = row.getAttribute("data-type") || "";
        var matchCat = activeCat === "todos" || rtype === activeCat;
        var matchTerm = !term || hay.indexOf(term) !== -1;
        var show = matchCat && matchTerm;
        row.style.display = show ? "" : "none";
        if (show) visible++;
      });
      if (emptyRow) emptyRow.classList.toggle("hidden", visible > 0 || rows.length === 0);
      if (counter) counter.textContent = visible + " de " + rows.length;
    };

    if (examFilter) {
      examFilter.addEventListener("input", applyResultFilters);
    }

    catButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        activeCat = btn.getAttribute("data-result-cat") || "todos";
        catButtons.forEach(function (b) {
          var selected = b === btn;
          b.setAttribute("aria-pressed", selected ? "true" : "false");
          b.className = selected
            ? "rounded-full bg-pine-950 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition cursor-pointer"
            : "rounded-full bg-sand-100 px-3.5 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-sand-200 cursor-pointer";
        });
        applyResultFilters();
      });
    });
  }

  // 6. Modal accesible <dialog> para cancelar citas
  var cancelDialog = document.getElementById("cancel-appt-dialog");
  if (cancelDialog) {
    var dialogApptId = document.getElementById("dialog-appt-id");
    var dialogDoctor = document.getElementById("dialog-appt-doctor");
    var dialogSlot = document.getElementById("dialog-appt-slot");

    document.querySelectorAll("[data-open-cancel]").forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        if (dialogApptId) dialogApptId.value = trigger.getAttribute("data-appt-id") || "";
        if (dialogDoctor) dialogDoctor.textContent = trigger.getAttribute("data-appt-doctor") || "";
        if (dialogSlot) dialogSlot.textContent = trigger.getAttribute("data-appt-slot") || "";
        if (typeof cancelDialog.showModal === "function") cancelDialog.showModal();
      });
    });

    cancelDialog.querySelectorAll("[data-close-dialog]").forEach(function (btn) {
      btn.addEventListener("click", function () { cancelDialog.close(); });
    });
    cancelDialog.addEventListener("click", function (e) {
      if (e.target === cancelDialog) cancelDialog.close();
    });
  }

  // 7. Lightbox DICOM / ECG en /paciente/ficha
  var lightbox = document.getElementById("imaging-lightbox");
  if (lightbox) {
    var lbImg = document.getElementById("lightbox-img");
    var lbTitle = document.getElementById("lightbox-title");
    var lbMeta = document.getElementById("lightbox-meta");

    document.querySelectorAll("[data-open-lightbox]").forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        if (lbImg) lbImg.src = trigger.getAttribute("data-lightbox-src") || "";
        if (lbTitle) lbTitle.textContent = trigger.getAttribute("data-lightbox-title") || "";
        if (lbMeta) lbMeta.textContent = trigger.getAttribute("data-lightbox-meta") || "";
        if (typeof lightbox.showModal === "function") lightbox.showModal();
      });
    });

    lightbox.querySelectorAll("[data-close-lightbox]").forEach(function (btn) {
      btn.addEventListener("click", function () { lightbox.close(); });
    });
    lightbox.addEventListener("click", function (e) {
      if (e.target === lightbox) lightbox.close();
    });
  }

  // 8. Modal de comprobante financiero en /paciente/pagos
  var billDialog = document.getElementById("bill-detail-dialog");
  if (billDialog) {
    document.querySelectorAll("[data-open-bill]").forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        var map = {
          "bill-folio": "data-bill-folio",
          "bill-date": "data-bill-date",
          "bill-desc": "data-bill-desc",
          "bill-unit": "data-bill-unit",
          "bill-total": "data-bill-total",
          "bill-ins": "data-bill-ins",
          "bill-copay": "data-bill-copay",
          "bill-method": "data-bill-method",
          "bill-status": "data-bill-status",
        };
        Object.keys(map).forEach(function (id) {
          var el = document.getElementById(id);
          if (el) el.textContent = trigger.getAttribute(map[id]) || "";
        });
        if (typeof billDialog.showModal === "function") billDialog.showModal();
      });
    });

    billDialog.querySelectorAll("[data-close-bill]").forEach(function (btn) {
      btn.addEventListener("click", function () { billDialog.close(); });
    });
    billDialog.addEventListener("click", function (e) {
      if (e.target === billDialog) billDialog.close();
    });
  }

  // 9. Toggle de contraseña con aria-pressed en /login
  var togglePassBtn = document.getElementById("toggle-pass-btn");
  var passInput = document.getElementById("password");
  if (togglePassBtn && passInput) {
    togglePassBtn.addEventListener("click", function () {
      var showing = passInput.type === "text";
      passInput.type = showing ? "password" : "text";
      togglePassBtn.textContent = showing ? "Mostrar" : "Ocultar";
      togglePassBtn.setAttribute("aria-pressed", showing ? "false" : "true");
    });
  }

  var firstInvalid = document.querySelector('[aria-invalid="true"]');
  if (firstInvalid) firstInvalid.focus();
})();
