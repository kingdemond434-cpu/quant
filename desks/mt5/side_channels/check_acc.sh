#!/bin/bash
echo "=== Twitter syndication API (no auth) ==="
timeout 10 curl -s "https://cdn.syndication.twimg.com/widgets/followbutton/info.json?screen_names=L1vsun,shmidt,cvxv666" | head -c 2000
echo
echo "=== xcancel.com (working Nitter fork) RSS ==="
timeout 15 curl -s "https://xcancel.com/L1vsun/rss" | head -c 1500
echo
echo "=== nitter.poast.org RSS ==="
timeout 15 curl -s "https://nitter.poast.org/L1vsun/rss" | head -c 1500
echo