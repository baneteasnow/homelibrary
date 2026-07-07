---
layout: page-6
published: true
title: "Category BiographyLifeStories"
category: "BiographyLifeStories"
---

{%- include backtotop.html -%}
<br />

<div style="clear: both"></div>
{%- assign items = site.data.list.item | default: site.data.list -%} {%- assign
category_items = items | where: "categories", page.category -%}

<table class="zebra">
	<tr>
		<th style="text-align: left">#</th>
		<th style="text-align: left">name of the book</th>
		<th style="text-align: left">author</th>
		<th style="text-align: left">location</th>
	</tr>

    	<td>{{ item.location }}</td>
    			<td>
    		<a
    			name="{{ item.title }}"
    			title="google search"
    			href="https://www.google.com/search?q={{ item.title }}%20{{ item.author }}"
    			target="_blank"
    			rel="noreferrer,nofollow"
    		>
    			google
    		</a>
    	</td>
    	<td>
    		<a
    			name="{{ item.title }}"
    			title="google search"
    			href="https://www.google.com/search?q={{ item.title }}%20{{ item.author }}&tbm=isch"
    			target="_blank"
    			rel="noreferrer,nofollow"
    		>
    			google images
    		</a>
    	</td>
    </tr>
    {%- endfor -%}

</table>

{%- assign items = site.data.list.item | default: site.data.list -%}
{%- assign category_items = items | where: "categpries", page.category -%}
