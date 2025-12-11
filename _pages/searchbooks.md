---
layout: page-11
title: kitap ara
published: true
---

<style>
	#search-container {
	    max-width: 100%;
	}

	input[type=text] {
		font-size: normal;
	    outline: none;
	    padding: 1rem;
		background: rgb(236, 237, 238);
	    width: 100%;
		-webkit-appearance: none;
		font-family: inherit;
		font-size: 100%;
		border: none;
	}
	#results-container {
		margin: .5rem 0;
	}
	#results-container .location {
	font-size: 0.8em;
	color: #888;
  }
</style>

<!-- Html Elements for Search -->
<div id="search-container">
<input type="text" id="search-input" placeholder="Search for a book...">
<ol id="results-container"></ol>
</div>

<!-- Script pointing to search-script.js -->
<script src="/search1.js" type="text/javascript"></script>

<!-- Configuration -->
<script type="text/javascript">
SimpleJekyllSearch({
  searchInput: document.getElementById('search-input'),
  resultsContainer: document.getElementById('results-container'),
  json: '/search.json',
  searchResultTemplate: '<div style="text-transform: lowercase;"><li><a href="{url}" title="{title}">{title}</a></li></div>',
  noResultsText: 'No results found',
  limit: 300000,
  fuzzy: false,
  exclude: ['Welcome']
})
</script>
<br />
<br />
<div style="clear: both;"></div>
