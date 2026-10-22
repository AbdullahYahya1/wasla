// Small line icons drawn for Wasla (no brand logos). All use currentColor.
window.WASLA_ICONS = (() => {
  const s = (body, box = "0 0 24 24") =>
    `<svg viewBox="${box}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
  return {
    logo: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect class="logo-bg" width="32" height="32" rx="9"/><path d="M7.5 19.5C8.5 5 23.5 5 24.5 18" fill="none" stroke="#FFB41F" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="0.6 4.12 0.6 4.12 0.6 4.12 0.6 4.12 0.6 40" stroke-dashoffset="-4.8"/><circle cx="7.5" cy="19.5" r="2.7" fill="#fff"/><circle cx="24.5" cy="19.5" r="4.6" fill="#FFB41F"/><circle class="logo-bg" cx="24.5" cy="19.5" r="1.9"/></svg>`,
    check: s('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
    android: s('<rect x="6" y="2.5" width="12" height="19" rx="2.6"/><circle cx="12" cy="5.3" r=".6" fill="currentColor"/><path d="M10 18.6h4"/>'),
    iphone: s('<rect x="6" y="2.5" width="12" height="19" rx="3.2"/><path d="M10.4 5h3.2"/>'),
    mac: s('<rect x="4" y="4.5" width="16" height="11" rx="1.6"/><path d="M2.5 19h19"/>'),
    key: s('<circle cx="8" cy="12" r="3.6"/><path d="M11.6 12H21M18 12v3M15 12v2.2"/>'),
    lock: s('<rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>'),
    plane: s('<path d="M10.5 13.5 4 12l-1-1.5 7.5-.5L14 3.5h1.8l-1.3 6.8 5.5.2 1.5-2h1.2l-.8 3.5.8 3.5h-1.2l-1.5-2-5.5.2 1.3 6.8H14L10.5 13.5Z"/>'),
    pin: s('<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/>'),
    chat: s('<path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-4.2A8 8 0 1 1 20 12Z"/>'),
    warn: s('<path d="M12 4 2.8 19.5h18.4L12 4Z"/><path d="M12 10v4.2"/><circle cx="12" cy="17" r=".5" fill="currentColor"/>'),
    shield: s('<path d="M12 3 5 6v5.5c0 4.3 3 8 7 9.5 4-1.5 7-5.2 7-9.5V6l-7-3Z"/><path d="m9 12 2.2 2.2L15.5 10"/>'),
    undo: s('<path d="M8 8H4V4"/><path d="M4.5 8.5A8 8 0 1 1 6 17.2"/>'),
    disk: s('<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>'),
    cloudoff: s('<path d="M3 3l18 18"/><path d="M8 8.2A5.5 5.5 0 0 0 6.5 19H17M20.6 16.8A4 4 0 0 0 17 10h-.6A6 6 0 0 0 10.6 6"/>'),
    phonebig: (ios) => `<svg viewBox="0 0 74 120" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true"><rect x="3" y="3" width="68" height="114" rx="${ios ? 16 : 10}"/>${ios ? '<rect x="27" y="10" width="20" height="6" rx="3" fill="currentColor" stroke="none"/>' : '<circle cx="37" cy="12" r="3" fill="currentColor" stroke="none"/>'}<path d="M18 40h24M18 50h36M18 60h28M18 70h33M18 80h20" stroke-width="3" stroke-linecap="round" opacity=".45"/></svg>`,
  };
})();
