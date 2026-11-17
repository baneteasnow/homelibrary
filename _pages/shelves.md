---
layout: page-11
title: bookshelves
published: true
---
{%- include backtotop.html -%}

<style>
.shelves-scroll { display: contents; }
.shelves-scroll-hint { display: none; }
.shelves-image-link { margin: 0 0 1rem; }

@media (max-width: 700px) {
  .w {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    padding-inline: 1rem;
  }
  .shelves-scroll {
    display: block;
    width: 100%;
    min-width: 0;
    overflow-x: auto;
    overscroll-behavior-x: contain;
  }
  .shelves-scroll table {
    width: max-content;
    max-width: none;
    border-collapse: separate;
    border-spacing: 0;
    border: 0;
    border-top: 1px solid #e2e2e2;
    border-left: 1px solid #e2e2e2;
    padding: 0;
  }
  .shelves-scroll :is(th, td) {
    box-sizing: border-box;
    width: 92px;
    min-width: 92px;
    white-space: nowrap;
    text-align: center;
    border: 0;
    border-right: 1px solid #e2e2e2;
    border-bottom: 1px solid #e2e2e2;
  }
  .shelves-scroll thead :is(th, td) { background: #f7f7f7; }
  .shelves-scroll :is(th, td):first-child {
    width: 36px;
    min-width: 36px;
    position: sticky;
    left: 0;
    z-index: 1;
    background: #f7f7f7;
  }
  .shelves-scroll a { white-space: nowrap; }
  .shelves-scroll-hint {
    display: block;
    margin: .5rem 0 0;
    color: #666;
    font-size: .85rem;
  }
}
</style>
<br />
<div class="shelves-image-link"><i><a href="https://homelibrary.next52books.com/shelf-images/">shelf-images</a></i></div>

{% capture shelves_img_open %}<div class="shelves-scroll" role="region" aria-label="Home G - img" tabindex="0">
<table>{% endcapture %}
{% capture shelves_img_close %}</table>
</div>
<p class="shelves-scroll-hint">↔ Scroll sideways to see more shelves</p>{% endcapture %}
{% capture shelves_img %}{% include g.html %}{% endcapture %}
{{ shelves_img | replace_first: '<table>', shelves_img_open | replace_first: '</table>', shelves_img_close }}

  <div style="clear: both"></div>
  <br />
{% capture shelves_list_open %}<div class="shelves-scroll" role="region" aria-label="Home G - List" tabindex="0">
<table>{% endcapture %}
{% capture shelves_list_close %}</table>
</div>
<p class="shelves-scroll-hint">↔ Scroll sideways to see more shelves</p>{% endcapture %}
{% capture shelves_list %}{% include g0.html %}{% endcapture %}
{{ shelves_list | replace_first: '<table>', shelves_list_open | replace_first: '</table>', shelves_list_close }}
<br />

  <div style="clear: both"></div>
<a href="https://homelibrary.next52books.com/shelves/shelves">shelves</a>
