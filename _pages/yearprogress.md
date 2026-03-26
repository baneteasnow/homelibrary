---
layout: page
title: "2026 year progress bar"
published: true
last_modified_at: 2026-03-23
---

<div class="year-progress-wrapper">
  <div class="year-progress-text" id="yearText"></div>
  <div class="year-progress-bar" title="2026">
    <div class="year-progress-fill" id="yearFill"></div>
  </div>
</div>

<style>
  .year-progress-wrapper {
    margin: 20px 0;
    font-size: 13px;
    color: #666;
  }

  .year-progress-text {
    margin-bottom: 6px;
    letter-spacing: 0.5px;
  }

  .year-progress-bar {
    width: 100%;
    height: 4px;
    background: #eee;
    border-radius: 2px;
    overflow: hidden;
  }

  .year-progress-fill {
    height: 100%;
    width: 0%;
    background: #111;
    transition: width 0.6s ease;
  }
</style>

<script>
  const now = new Date();

  const start = new Date(now.getFullYear(), 0, 0);
  const end = new Date(now.getFullYear(), 11, 31);

  const oneDay = 1000 * 60 * 60 * 24;

  const dayOfYear = Math.floor((now - start) / oneDay);
  const totalDays = Math.floor((end - start) / oneDay);

  const firstDayOfYear = new Date(now.getFullYear(), 0, 1);
  const pastDays = Math.floor((now - firstDayOfYear) / oneDay);
  const weekOfYear = Math.ceil((pastDays + firstDayOfYear.getDay() + 1) / 7);

  const progressPercent = (dayOfYear / totalDays) * 100;
  const remainingPercent = (100 - progressPercent).toFixed(1);
  const remainingDays = totalDays - dayOfYear;
  const dayLabel = remainingDays === 1 ? "day" : "days";

  document.getElementById("yearFill").style.width = progressPercent + "%";
  document.getElementById("yearText").innerHTML =
    `Day ${dayOfYear} · Week ${weekOfYear} — ${remainingPercent}% · ${remainingDays} ${dayLabel} left`;
</script>
