(function () {
  const D = window.ROAS_DATA;
  const CHECKS = window.ROAS_CHECKS.map(([node, r, q, where, bad, todo, basis, flag]) => ({ node, r, q, where, bad, todo, basis, flag: !!flag }));
  const L = Object.fromEntries(D.layers.map(l => [l.id, l]));
  const NODE = {};
  D.layers.forEach(l => {
    l.nodes.forEach(n => { NODE[n.id] = { ...n, layer: l }; });
    if (l.rail) NODE[l.rail.id] = { ...l.rail, layer: l };
    if (l.cross) NODE[l.cross.id] = { ...l.cross, layer: l };
  });
  NODE.G = { id: "G", name: "신호판", layer: { id: "G", name: "신호판" } };
  const state = { rhythm: "all", J: "J1", M: "M1", demo: 0 };

  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const of = (node, r) => CHECKS.filter(c => c.node === node && (!r || c.r === r));
  const shown = r => state.rhythm === "all" || state.rhythm === r;

  function seg(box, opts, get, set) {
    box.innerHTML = "";
    opts.forEach(o => {
      const b = document.createElement("button");
      b.textContent = o.label;
      b.setAttribute("aria-pressed", String(get() === o.id));
      b.addEventListener("click", () => { set(o.id); seg(box, opts, get, set); });
      box.appendChild(b);
    });
  }

  // ── 점검 카드
  function card(c) {
    const b = D.basis[c.basis];
    return `<div class="chk"><div class="top"><div class="q">${esc(c.q)}</div><span class="basis" title="${esc(b.desc)}">${esc(b.name)}</span></div>
      <dl><dt>보는 곳</dt><dd>${esc(c.where)}</dd><dt>이상 신호</dt><dd>${esc(c.bad)}</dd><dt>할 일</dt><dd class="do">${esc(c.todo)}</dd></dl>
      ${c.flag ? '<div class="flag">메타 필드 이름 확인 필요</div>' : ""}</div>`;
  }
  function columns(node) {
    const rs = ["D", "W"].filter(shown);
    return `<div class="cols ${rs.length === 1 ? "one" : ""}">` + rs.map(r => {
      const list = of(node, r);
      return `<div><div class="col-head ${r}"><b>${D.rhythms[r].name}</b><span class="muted small">${D.rhythms[r].sub}</span></div>
        ${list.length ? list.map(card).join("") : `<div class="none">${r === "D" ? "매일 볼 고정값이 없는 자리" : "매주 볼 흐름이 없는 자리"}</div>`}</div>`;
    }).join("") + "</div>";
  }
  function counts(node) {
    return ["D", "W"].filter(shown).map(r => `<span class="n ${r}">${D.rhythms[r].name} ${of(node, r).length}</span>`).join(" ");
  }
  function panel(boxId, node) {
    const n = NODE[node];
    const where = n.layer.id === "G" ? "신호판" : `${n.layer.name} › ${n.name}`;
    $(boxId).innerHTML = `<div class="panel-head"><h3>${esc(where)}</h3>${n.hint ? `<span class="muted small">${esc(n.hint)}</span>` : ""}</div>${columns(node)}`;
  }

  // ── 한눈에
  function renderGlance() {
    const chipLinks = (l, href) => l.nodes.map(n => `<a class="chip" href="${href}" data-node="${n.id}">${esc(n.name)}</a>`).join("") +
      (l.rail ? `<a class="chip" href="${href}" data-node="${l.rail.id}">${esc(l.rail.name)}</a>` : "") +
      (l.cross ? `<a class="chip" href="${href}" data-node="${l.cross.id}">${esc(l.cross.name)}</a>` : "");
    const head = l => `<div class="nest-head"><b>${l.name}</b><span class="tag ${l.id}">${l.lens}</span><span class="q">${esc(l.ask)}</span><span class="shape">여기가 원인이면 — ${esc(l.shape)}</span></div>`;
    const S = L.S, J = L.J, M = L.M;
    $("#glance-box").innerHTML = `
      <div class="flow-top"><a class="card" href="#signal" style="text-decoration:none;color:inherit"><b>① 신호판</b> — 정말 떨어졌나 · 어느 숫자가 끌어내렸나 · 업종도? 자사몰도?</a></div>
      <div class="arrow-down">② 바깥에서 안으로 원인 자리를 찾는다 ↓</div>
      <div class="nest">${head(S)}<span class="outer-note">가장 바깥</span><div class="chips">${chipLinks(S, "#market")}</div>
        <div class="in J">${head(J)}<div class="chips">${chipLinks(J, "#own")}</div>
          <div class="in M">${head(M)}<div class="chips">${chipLinks(M, "#media")}</div></div>
        </div>
      </div>
      <div class="arrow-down">③ 찾은 자리에서 ↓</div>
      <div class="flow-bottom">${["D", "W"].map(r => `<div class="card"><span class="tag ${r}">${D.rhythms[r].name}</span> <b>${D.rhythms[r].sub}</b>
        <p class="muted small" style="margin:6px 0 0">${D.rhythms[r].when} → <b style="color:var(--text)">${D.rhythms[r].out}</b></p></div>`).join("")}</div>`;
    document.querySelectorAll("#glance-box a.chip").forEach(a => a.addEventListener("click", () => {
      const id = a.dataset.node, lay = id[0];
      if (lay === "J" || lay === "M") { state[lay] = id; lay === "J" ? renderOwn() : renderMedia(); }
    }));
  }

  // ── 신호판
  function renderSignal() {
    $("#tiles").innerHTML = D.tiles.map(t => `<div class="card tile"><span class="k">${esc(t.k)}</span><span class="dir">${t.dir}</span>
      <div class="why">${esc(t.why)}</div><div class="to">어디부터 → ${esc(t.to)}</div></div>`).join("");
    panel("#panel-G", "G");
  }

  // ── 시장
  function renderMarket() {
    const S = L.S;
    $("#market-sub").innerHTML = `${esc(S.ask)} — 가장 바깥 레이어. 대부분 위클리로 보고, 데일리에는 '오늘이 특별한 날인지 · 다 같이 떨어졌는지 · 메타에 장애가 있는지'만 본다.`;
    $("#macro").innerHTML = S.nodes.map(n => {
      const list = CHECKS.filter(c => c.node === n.id && shown(c.r));
      return `<div class="card"><h3>${esc(n.name)}</h3><p class="muted small">${esc(n.hint)}</p>
        ${list.map(c => `<div style="margin-top:8px"><span class="tag ${c.r}">${D.rhythms[c.r].name}</span></div>${card(c)}`).join("") || '<div class="none">이 보기에는 점검이 없다</div>'}</div>`;
    }).join("");
  }

  // ── 자사 · 웹 상태
  function renderOwn() {
    const J = L.J;
    $("#own-sub").innerHTML = `${esc(J.ask)} — 손님이 지나는 자리마다 '열리나 · 살 수 있나 · 잡히나'를 본다. 자리를 누르면 아래에 점검이 열린다.`;
    $("#path").innerHTML = J.nodes.map(n => `<div class="stop"><button aria-pressed="${state.J === n.id}" data-id="${n.id}">
      <span class="nm">${esc(n.name)}</span><span class="hint">${esc(n.hint)}</span><span class="cnt">${counts(n.id)}</span></button>
      <div class="ev">${esc(n.event)}</div></div>`).join("");
    $("#rail").innerHTML = `<button aria-pressed="${state.J === J.rail.id}" data-id="${J.rail.id}"><b>${esc(J.rail.name)}</b> <span class="muted small">— ${esc(J.rail.hint)}</span> <span class="cnt">${counts(J.rail.id)}</span></button>`;
    document.querySelectorAll("#path button, #rail button").forEach(b => b.addEventListener("click", () => { state.J = b.dataset.id; renderOwn(); }));
    panel("#panel-J", state.J);
  }

  // ── 매체 · 메타 구조
  function renderMedia() {
    const M = L.M;
    $("#media-sub").innerHTML = `${esc(M.ask)} — 위에서 아래로 갈수록 개수가 많아진다. 원인 자리는 잃은 매출이 몰린 쪽으로 내려가며 찾는다.`;
    $("#tree").innerHTML = M.nodes.map((n, k) => `<div class="tnode ${k === 0 ? "one" : k >= 2 ? "lots" : ""}"><button aria-pressed="${state.M === n.id}" data-id="${n.id}">
      <span class="many">${esc(n.many)}</span><span class="nm">${esc(n.name)}</span><span class="hint">${esc(n.hint)}</span><span class="cnt">${counts(n.id)}</span></button></div>`).join("");
    $("#crossbar").innerHTML = `<button aria-pressed="${state.M === M.cross.id}" data-id="${M.cross.id}"><b>${esc(M.cross.name)}</b> <span class="muted small">— ${esc(M.cross.hint)}</span> <span class="cnt">${counts(M.cross.id)}</span></button>`;
    $("#ghost").textContent = `지금은 ${M.now}. ${M.later.join(" · ")}도 같은 모양(계정 → 캠페인 → 광고 묶음 → 광고)으로 옆에 붙는다.`;
    document.querySelectorAll("#tree button, #crossbar button").forEach(b => b.addEventListener("click", () => { state.M = b.dataset.id; renderMedia(); }));
    panel("#panel-M", state.M);
  }

  // ── 예시
  const NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, parent) { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); parent.appendChild(n); return n; }
  function tx(p, x, y, s, cls, anchor) { const t = el("text", { x, y, class: cls || "", "text-anchor": anchor || "start" }, p); t.textContent = s; return t; }
  const TRAIL = [["start", "정말 떨어졌나"], ["market", "시장"], ["own", "자사"], ["acc", "계정 → 캠페인"], ["B", "캠페인 → 광고세트"], ["found", "원인 자리"]];
  function renderDemo() {
    const st = D.demo.steps[state.demo], at = st.at, idx = TRAIL.findIndex(t => t[0] === at);
    $("#trail").innerHTML = TRAIL.map((t, k) => `<span class="${k === idx ? "on" : k < idx ? "done" : ""}">${k < idx ? "✓ " : ""}${t[1]}</span>`).join("");
    const svg = $("#demo-svg"); svg.innerHTML = "";
    const T = D.demo.tree;
    const box = { acc: { x: 390, y: 8, w: 220 } };
    const cx = [40, 385, 730];
    T.camps.forEach((c, i) => {
      box[c.k] = { x: cx[i], y: 118, w: 230, d: c };
      c.sets.forEach((s, j) => { box[s[0]] = { x: cx[i] - 30 + j * 165, y: 238, w: 150, s }; });
    });
    const H = 58, mid = b => b.x + b.w / 2;
    T.camps.forEach(c => {
      el("path", { d: `M${mid(box.acc)},${box.acc.y + H} C${mid(box.acc)},${box.acc.y + H + 26} ${mid(box[c.k])},${box[c.k].y - 26} ${mid(box[c.k])},${box[c.k].y}`, class: "edge" }, svg);
      c.sets.forEach(s => el("path", { d: `M${mid(box[c.k])},${box[c.k].y + H} C${mid(box[c.k])},${box[c.k].y + H + 26} ${mid(box[s[0]])},${box[s[0]].y - 26} ${mid(box[s[0]])},${box[s[0]].y}`, class: "edge" }, svg));
    });
    const look = {
      start: { focus: ["acc"] }, market: {}, own: {},
      acc: { focus: ["acc"], hot: ["B"], calm: ["A", "C"], bars: ["A", "B", "C"] },
      B: { focus: ["B"], hot: ["B-1 · 신규", "B-2 · 관심사"], calm: ["A", "C", "A-1", "A-2", "C-1"], bars: ["B-1 · 신규", "B-2 · 관심사"] },
      found: { hot: ["B"], calm: ["A", "C", "A-1", "A-2", "C-1", "B-1 · 신규", "B-2 · 관심사"] }
    }[at];
    const has = (k, key) => (look[key] || []).includes(k);
    Object.keys(box).forEach(k => {
      const b = box[k];
      const title = k === "acc" ? T.acc.t : b.d ? b.d.t : b.s[0];
      const sub = k === "acc" ? T.acc.v : b.d ? b.d.v : b.s[1];
      const share = b.d ? b.d.share : b.s ? b.s[2] : null;
      const g = el("g", { class: ["tn", has(k, "focus") && "focus", has(k, "hot") && "hot", has(k, "calm") && "calm"].filter(Boolean).join(" ") }, svg);
      el("rect", { x: b.x, y: b.y, width: b.w, height: H, rx: 10, class: "body" }, g);
      tx(g, b.x + 10, b.y + 22, title);
      tx(g, b.x + 10, b.y + 40, sub, "v");
      if (has(k, "bars") && share != null) {
        el("rect", { x: b.x + 10, y: b.y + 47, width: b.w - 20, height: 5, rx: 2.5, class: "share-bg" }, g);
        el("rect", { x: b.x + 10, y: b.y + 47, width: (b.w - 20) * share / 100, height: 5, rx: 2.5, class: "share" }, g);
        tx(g, b.x + b.w - 10, b.y + 22, `몫 ${share}%`, "v", "end");
      }
    });
    $("#demo-msg").textContent = st.msg;
    $("#demo-prev").disabled = state.demo === 0;
    $("#demo-next").disabled = state.demo === D.demo.steps.length - 1;
  }

  // ── 알림 · 원인 읽기 · 부록
  function renderRest() {
    $("#alert-box").innerHTML = ["D", "W"].map(r => `<div class="card"><span class="tag ${r}">${D.rhythms[r].name}</span><div class="msg" style="margin-top:8px">${D.alerts[r].map(s => `<div>${esc(s)}</div>`).join("")}</div></div>`).join("");
    $("#pattern-table").innerHTML = `<thead><tr><th>이렇게 읽는다</th><th>같이 움직인 숫자</th><th>원인 자리</th><th>바꿀 방향</th></tr></thead><tbody>` +
      D.patterns.map(p => `<tr><td data-k="이렇게 읽는다"><b>${esc(p[0])}</b></td><td data-k="같이 움직인 숫자">${esc(p[1])}</td><td data-k="원인 자리">${esc(p[2])}</td><td data-k="바꿀 방향">${esc(p[3])}</td></tr>`).join("") + "</tbody>";
    const bs = r => Object.values(D.basis).filter(b => b.r === r).map(b => `<li><b>${esc(b.name)}</b> — ${esc(b.desc)}</li>`).join("");
    $("#basis-box").innerHTML = `<p class="small">업종 · 광고주 표준값이 아직 없다. 그래서 바깥 기준 대신 <b>늘 맞아야 하는 규칙</b>과 <b>그 계정 자신의 기록</b>으로 판정하고, 표준값은 쌓아서 만든다.</p>
      <div class="basis-grid"><div><span class="tag D">데일리</span><ul class="tight small" style="margin-top:6px">${bs("D")}</ul></div><div><span class="tag W">위클리</span><ul class="tight small" style="margin-top:6px">${bs("W")}</ul></div></div>`;
    $("#learn").innerHTML = D.appendix.learn.map(s => `<li class="small">${esc(s)}</li>`).join("");
    $("#illusion-box").innerHTML = D.appendix.illusions.map(i => `<p class="small"><b>${esc(i[0])}</b> — ${esc(i[1])}</p>`).join("");
    $("#collect-table").innerHTML = `<thead><tr><th>어디서</th><th>무엇을</th><th>쓰는 자리</th><th>얼마나 자주</th></tr></thead><tbody>` +
      D.appendix.collect.map(c => `<tr><td data-k="어디서"><b>${esc(c[0])}</b></td><td data-k="무엇을">${esc(c[1])}</td><td data-k="쓰는 자리">${esc(c[2])}</td><td data-k="얼마나 자주">${esc(c[3])}</td></tr>`).join("") + "</tbody>";
    const f = D.appendix.fields;
    $("#fields").innerHTML = `<p class="small"><b>확인됨</b> — ${esc(f.ok)}</p><p class="small"><b>확인 필요</b> — ${esc(f.todo)}</p><p class="small"><b>주의</b> — ${esc(f.warn)}</p>`;
  }

  // ── 기능으로 담기
  function renderProduct() {
    const P = D.product;
    $("#product-pitch").textContent = P.pitch;
    $("#doors").innerHTML = P.doors.map((d, k) => `<div class="card door"><h3>${k + 1}. ${esc(d.name)}</h3>
      <div class="meta"><span class="chip">${esc(d.where)}</span><span class="chip">${esc(d.who)}</span><span class="chip">${esc(d.when)}</span></div>
      <dl><dt>하는 일</dt><dd>${esc(d.what)}</dd><dt>왜</dt><dd>${esc(d.why)}</dd><dt>마케터</dt><dd>${esc(d.human)}</dd></dl></div>`).join("");
    $("#engine").innerHTML = P.engine.map(e => `<div class="eng"><div class="card"><b>${esc(e[0])}</b><div class="who">${esc(e[2])}</div><p class="small" style="margin:4px 0 0">${esc(e[1])}</p></div></div>`).join("");
    $("#result-table").innerHTML = "<tbody>" + P.result.map(r => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td></tr>`).join("") + "</tbody>";
    const st = Object.fromEntries(P.states.map(s => [s.id, s]));
    $("#board-title").textContent = P.board.title;
    $("#board").innerHTML = P.board.rows.map(([lid, nodes]) => `<div class="brow"><div class="lname">${esc(L[lid].name)}</div><div class="lights">${nodes.map(([nid, s]) =>
      `<span class="light ${s}" title="${esc(st[s].name)}"><i></i>${esc(NODE[nid].name)}</span>`).join("")}</div></div>`).join("") +
      `<ul class="tight small" style="margin-top:10px">${P.board.notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul>` +
      `<div class="legend-row">${P.states.map(s => `<span class="light ${s.id}"><i></i>${esc(s.name)} <span class="muted">— ${esc(s.desc)}</span></span>`).join("")}</div>`;
    $("#fit-table").innerHTML = `<thead><tr><th>잡혀 있던 과제</th><th>이 지도의 어느 점검</th><th>관계</th></tr></thead><tbody>` +
      P.fit.map(f => `<tr><td data-k="잡혀 있던 과제"><b>${esc(f[0])}</b></td><td data-k="이 지도의 어느 점검">${esc(f[1])}</td><td data-k="관계">${esc(f[2])}</td></tr>`).join("") + "</tbody>";
    $("#phase-table").innerHTML = `<thead><tr><th>단계</th><th>무엇을</th><th>열리는 입구</th></tr></thead><tbody>` +
      P.phases.map(p => `<tr><td data-k="단계"><b>${esc(p[0])}. ${esc(p[1])}</b></td><td data-k="무엇을">${esc(p[2])}</td><td data-k="열리는 입구">${esc(p[3])}</td></tr>`).join("") + "</tbody>";
  }

  function initTheme() {
    let saved = null;
    try { saved = localStorage.getItem("roas-map-theme"); } catch (e) {}
    if (saved) document.documentElement.setAttribute("data-theme", saved);
    $("#theme-toggle").addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("roas-map-theme", next); } catch (e) {}
    });
  }

  function renderAll() { renderSignal(); renderMarket(); renderOwn(); renderMedia(); }
  seg($("#rhythm-seg"), [{ id: "all", label: "둘 다" }, { id: "D", label: "데일리" }, { id: "W", label: "위클리" }], () => state.rhythm, v => { state.rhythm = v; renderAll(); });
  renderGlance(); renderAll(); renderDemo(); renderRest(); renderProduct(); initTheme();
  $("#demo-next").addEventListener("click", () => { if (state.demo < D.demo.steps.length - 1) { state.demo++; renderDemo(); } });
  $("#demo-prev").addEventListener("click", () => { if (state.demo > 0) { state.demo--; renderDemo(); } });
  $("#demo-reset").addEventListener("click", () => { state.demo = 0; renderDemo(); });
})();
