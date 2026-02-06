---
layout: home
title: "TheRichWay - 미국 주식 리포트"
---

# 📊 미국 증시 데일리 리포트
**냉철한 데이터 분석가가 전하는 시장의 핵심 시그널**

현재 시장의 흐름과 주요 지수 분석을 확인하세요.

---

## 최신 분석 리포트
<ul>
  {% for post in site.posts %}
    {% if post.published != false %}
      <li>
        <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
        <small>({{ post.date | date: "%Y-%m-%d" }})</small>
      </li>
    {% endif %}
  {% endfor %}
</ul>

{% if site.posts.size == 0 %}
<p>현재 준비된 분석 리포트가 없습니다. 잠시만 기다려 주세요!</p>
{% endif %}