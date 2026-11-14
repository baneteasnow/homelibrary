/* Keep a subtle scrollbar visible only when the table actually overflows. */
(() => {
  function init(wrapper) {
    const table = wrapper.querySelector('table');
    const indicator = wrapper.querySelector('.hl-scroll-indicator');
    const thumb = indicator?.querySelector('.hl-scroll-thumb');
    if (!table || !indicator || !thumb) return;
    let scheduled = false;
    function update() {
      scheduled = false;
      const viewport = wrapper.clientWidth;
      const total = wrapper.scrollWidth;
      const visible = window.matchMedia('(max-width: 768px)').matches && table.getClientRects().length > 0 && total > viewport + 2;
      indicator.classList.toggle('is-visible', visible);
      if (!visible) return;
      const thumbWidth = Math.max(12, viewport * viewport / total);
      thumb.style.width = `${Math.min(viewport, thumbWidth)}px`;
      const maxTravel = Math.max(0, viewport - thumbWidth);
      const maxScroll = total - viewport;
      thumb.style.transform = `translateX(${maxTravel * wrapper.scrollLeft / maxScroll}px)`;
    }
    function queue() { if (!scheduled) { scheduled = true; requestAnimationFrame(update); } }
    wrapper.addEventListener('scroll', queue, {passive:true});
    window.addEventListener('resize', queue, {passive:true});
    if ('ResizeObserver' in window) {
      const observer = new ResizeObserver(queue);
      observer.observe(wrapper);
      observer.observe(table);
    }
    if ('MutationObserver' in window) {
      new MutationObserver(queue).observe(table, {attributes:true, attributeFilter:['style','class'], childList:true, subtree:true});
    }
    queue();
  }
  function start() { document.querySelectorAll('[data-hl-table-scroll]').forEach(init); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
