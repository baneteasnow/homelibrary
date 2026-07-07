---
layout: page-6
published: true
title: "category TechnologyTheDigitalWorld"
category: "TechnologyTheDigitalWorld"
---

{%- include backtotop.html -%}
<br />

<div style="clear: both"></div>
{%- assign items = site.data.list.item | default: site.data.list -%}
{%- assign category_items = items | where: "categories", page.category -%}

<table class="zebra">
	<tr>
		<th style="text-align: left">#</th>
		<th style="text-align: left">name of the book</th>
		<th style="text-align: left">author</th>
		<th style="text-align: left">shelf</th>
		<th style="text-align: left">location</th>
	</tr>

    {%- for item in category_items -%}
    <tr>
    	<td>{{ item.bookshelf }}</td>
    	<td>
    		<a href="{{ site.baseurl }}/booklist#{{ item.bookshelf }}">
    			<b>{{ item.title }}</b>
    		</a>
    	</td>
    	<td>{{ item.author }}</td>
    	<td>{{ item.notes }}</td>
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
    			title="google images search"
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
