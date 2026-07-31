---
layout: page-8
published: true
title: "category BiographyLifeStories"
category: "BiographyLifeStories"
---

{%- include backtotop.html -%}
<br />

<div style="clear: both"></div>

{%- assign items = site.data.list.item | default: site.data.list -%}
{%- assign category_items = items | where: "categories", page.category -%}

<p>{{ category_items | size }}</p>
<div style="clear: both"></div>

<table class="zebra">
	<thead>
		<tr>
			<th style="text-align: left">#</th>
			<th style="text-align: left">name of the book</th>
			<th style="text-align: left">author</th>
			<th style="text-align: left">shelf</th>
			<th style="text-align: left">location</th>
			<th style="text-align: left">search</th>
			<th style="text-align: left">images</th>
		</tr>
	</thead>

    <tbody>
    	{%- for item in category_items -%}
    	<tr>
    		<td>{{ item.bookshelf }}</td>

    		<td>
    			<a href="{{ '/booklist' | relative_url }}#{{ item.bookshelf }}">
    				<b>{{ item.title }}</b>
    			</a>
    		</td>

    		<td>{{ item.author }}</td>
    		<td>{{ item.notes }}</td>
    		<td>{{ item.location }}</td>

    		<td>
    			<a
    				title="google search"
    				href="https://www.google.com/search?q={{ item.title | append: ' ' | append: item.author | url_encode }}"
    				target="_blank"
    				rel="noopener noreferrer nofollow"
    			>
    				google
    			</a>
    		</td>

    		<td>
    			<a
    				title="google images search"
    				href="https://www.google.com/search?tbm=isch&q={{ item.title | append: ' ' | append: item.author | url_encode }}"
    				target="_blank"
    				rel="noopener noreferrer nofollow"
    			>
    				google images
    			</a>
    		</td>
    	</tr>
    	{%- endfor -%}
    </tbody>

</table>
