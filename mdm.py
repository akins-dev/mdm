#!/usr/bin/env python3
"""Moment distribution method for continuous beams.

Sign convention used in this program:
    Clockwise member-end moments are positive.

Supported span loads:
    - uniformly distributed load over the full span
    - point load at any distance from the left support

Relative member stiffness is taken as 1/L, as requested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Iterable, List, Tuple


@dataclass
class Span:
    left: str
    right: str
    length: float
    udl: float = 0.0
    point_loads: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.left}{self.right}"

    @property
    def stiffness(self) -> float:
        return 1.0 / self.length

    @property
    def left_end(self) -> str:
        return f"{self.left}{self.right}"

    @property
    def right_end(self) -> str:
        return f"{self.right}{self.left}"

    def fixed_end_moments(self) -> Tuple[float, float]:
        """Return fixed-end moments (left end, right end)."""
        fem_left = -(self.udl * self.length**2) / 12.0
        fem_right = (self.udl * self.length**2) / 12.0

        for load, a in self.point_loads:
            b = self.length - a
            fem_left += -(load * b**2 * a) / self.length**2
            fem_right += (load * a**2 * b) / self.length**2

        return fem_left, fem_right

    def fixed_end_detail_rows(self) -> List[List[str]]:
        rows: List[List[str]] = []
        if self.udl:
            left_value = -(self.udl * self.length**2) / 12.0
            right_value = (self.udl * self.length**2) / 12.0
            rows.append(
                [
                    self.name,
                    "UDL",
                    self.left_end,
                    "-wL^2/12",
                    f"-({fmt(self.udl)} x {fmt(self.length)}^2) / 12",
                    money(left_value),
                ]
            )
            rows.append(
                [
                    self.name,
                    "UDL",
                    self.right_end,
                    "wL^2/12",
                    f"({fmt(self.udl)} x {fmt(self.length)}^2) / 12",
                    money(right_value),
                ]
            )

        for index, (load, a) in enumerate(self.point_loads, start=1):
            b = self.length - a
            left_value = -(load * b**2 * a) / self.length**2
            right_value = (load * a**2 * b) / self.length**2
            rows.append(
                [
                    self.name,
                    f"Point {index}",
                    self.left_end,
                    "-Pab^2/L^2",
                    f"-({fmt(load)} x {fmt(a)} x {fmt(b)}^2) / {fmt(self.length)}^2",
                    money(left_value),
                ]
            )
            rows.append(
                [
                    self.name,
                    f"Point {index}",
                    self.right_end,
                    "Pa^2b/L^2",
                    f"({fmt(load)} x {fmt(a)}^2 x {fmt(b)}) / {fmt(self.length)}^2",
                    money(right_value),
                ]
            )

        if not rows:
            rows.append([self.name, "No load", self.left_end, "0", "0", money(0.0)])
            rows.append([self.name, "No load", self.right_end, "0", "0", money(0.0)])

        left_total, right_total = self.fixed_end_moments()
        rows.append([self.name, "Total", self.left_end, "sum", "sum of left-end contributions", money(left_total)])
        rows.append([self.name, "Total", self.right_end, "sum", "sum of right-end contributions", money(right_total)])
        return rows


def support_names(count: int) -> List[str]:
    names = []
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i in range(count):
        if i < len(alphabet):
            names.append(alphabet[i])
        else:
            names.append(f"S{i + 1}")
    return names


def read_float(prompt: str, minimum: float | None = None, default: float | None = None) -> float:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("Enter a valid number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Enter a value greater than or equal to {minimum}.")
            continue
        return value


def read_int(prompt: str, minimum: int | None = None, default: int | None = None) -> int:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Enter a valid whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Enter a value greater than or equal to {minimum}.")
            continue
        return value


def read_yes_no(prompt: str, default: bool = True) -> bool:
    default_text = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{default_text}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Enter y or n.")


def money(value: float) -> str:
    if abs(value) < 0.0000005:
        value = 0.0
    return f"{value:,.4f}"


def fmt(value: float) -> str:
    return f"{value:g}"


def print_table(headers: List[str], rows: Iterable[Iterable[object]]) -> None:
    string_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in string_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def line(left: str, fill: str, middle: str, right: str) -> str:
        return left + middle.join(fill * (width + 2) for width in widths) + right

    print(line("+", "-", "+", "+"))
    print("| " + " | ".join(header.ljust(widths[i]) for i, header in enumerate(headers)) + " |")
    print(line("+", "-", "+", "+"))
    for row in string_rows:
        print("| " + " | ".join(cell.rjust(widths[i]) for i, cell in enumerate(row)) + " |")
    print(line("+", "-", "+", "+"))


def build_distribution_rows(
    spans: List[Span],
    supports: List[str],
    fixed_supports: set[str],
) -> Tuple[List[List[str]], Dict[str, float], Dict[str, List[str]], Dict[str, str]]:
    joint_ends: Dict[str, List[str]] = {support: [] for support in supports}
    end_to_span: Dict[str, Span] = {}
    opposite: Dict[str, str] = {}

    for span in spans:
        joint_ends[span.left].append(span.left_end)
        joint_ends[span.right].append(span.right_end)
        end_to_span[span.left_end] = span
        end_to_span[span.right_end] = span
        opposite[span.left_end] = span.right_end
        opposite[span.right_end] = span.left_end

    distribution_factors: Dict[str, float] = {}
    rows: List[List[str]] = []

    for joint in supports:
        total_stiffness = 0.0 if joint in fixed_supports else sum(end_to_span[end].stiffness for end in joint_ends[joint])
        for end in joint_ends[joint]:
            span = end_to_span[end]
            df = 0.0 if total_stiffness == 0 else span.stiffness / total_stiffness
            distribution_factors[end] = df
            rows.append(
                [
                    joint,
                    span.name,
                    end,
                    money(span.stiffness),
                    money(total_stiffness),
                    money(df),
                ]
            )

    return rows, distribution_factors, joint_ends, opposite


def moment_distribution(
    spans: List[Span],
    supports: List[str],
    fixed_supports: set[str],
    distribution_factors: Dict[str, float],
    joint_ends: Dict[str, List[str]],
    opposite: Dict[str, str],
    tolerance: float,
    max_cycles: int,
) -> Tuple[List[str], List[List[str]], Dict[str, float], int]:
    end_labels = [end for span in spans for end in (span.left_end, span.right_end)]
    moments = {end: 0.0 for end in end_labels}

    for span in spans:
        left_fem, right_fem = span.fixed_end_moments()
        moments[span.left_end] = left_fem
        moments[span.right_end] = right_fem

    rows: List[List[str]] = [
        ["Fixed-end moments"] + [money(moments[end]) for end in end_labels],
    ]

    cycles_used = 0
    for cycle in range(1, max_cycles + 1):
        cycles_used = cycle
        cycle_changed = False

        for joint in supports:
            if joint in fixed_supports:
                continue

            unbalanced = sum(moments[end] for end in joint_ends[joint])
            if abs(unbalanced) <= tolerance:
                continue

            cycle_changed = True
            balance_row = {end: 0.0 for end in end_labels}
            carry_row = {end: 0.0 for end in end_labels}

            for end in joint_ends[joint]:
                distributed = -unbalanced * distribution_factors[end]
                balance_row[end] += distributed
                moments[end] += distributed

            for end in joint_ends[joint]:
                carried = balance_row[end] * 0.5
                other_end = opposite[end]
                carry_row[other_end] += carried
                moments[other_end] += carried

            rows.append([f"Cycle {cycle}: balance {joint}"] + [money(balance_row[end]) for end in end_labels])
            rows.append([f"Cycle {cycle}: carry-over {joint}"] + [money(carry_row[end]) for end in end_labels])

        max_unbalanced = 0.0
        for joint in supports:
            if joint not in fixed_supports:
                max_unbalanced = max(max_unbalanced, abs(sum(moments[end] for end in joint_ends[joint])))

        if max_unbalanced <= tolerance or not cycle_changed:
            break

    rows.append(["Final moments"] + [money(moments[end]) for end in end_labels])
    return ["Step"] + end_labels, rows, moments, cycles_used


def support_moment_rows(
    supports: List[str],
    joint_ends: Dict[str, List[str]],
    moments: Dict[str, float],
) -> List[List[str]]:
    rows = []
    for joint in supports:
        end_values = ", ".join(f"{end}={money(moments[end])}" for end in joint_ends[joint])
        rows.append([joint, end_values, money(sum(moments[end] for end in joint_ends[joint]))])
    return rows


APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hardy Cross Moment Distribution</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --line: #d9e0e7;
      --text: #1b2430;
      --muted: #667085;
      --accent: #1264a3;
      --accent-dark: #0d4d7d;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 14px;
    }
    header {
      padding: 16px 22px;
      background: #16202a;
      color: #fff;
    }
    h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0;
    }
    main {
      display: grid;
      grid-template-columns: minmax(340px, 430px) minmax(0, 1fr);
      gap: 14px;
      padding: 14px;
      height: calc(100vh - 56px);
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .inputs {
      display: flex;
      flex-direction: column;
      min-height: 0;
    }
    .section {
      padding: 14px;
      border-bottom: 1px solid var(--line);
    }
    .section:last-child { border-bottom: 0; }
    h2 {
      margin: 0 0 10px;
      font-size: 15px;
    }
    label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }
    input[type="number"], input[type="text"] {
      width: 100%;
      border: 1px solid #cfd7df;
      border-radius: 6px;
      padding: 8px;
      font: inherit;
      background: #fff;
    }
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      vertical-align: middle;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .span-list {
      overflow: auto;
      padding: 12px 14px;
      min-height: 0;
      flex: 1;
    }
    .span-row {
      display: grid;
      grid-template-columns: 52px 1fr 1fr;
      gap: 8px;
      align-items: end;
      margin-bottom: 10px;
    }
    .span-row .points { grid-column: 2 / 4; }
    .span-name {
      align-self: center;
      font-weight: 700;
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      padding: 14px;
      border-top: 1px solid var(--line);
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    .primary {
      background: var(--accent);
      color: #fff;
    }
    .primary:hover { background: var(--accent-dark); }
    .secondary {
      background: #e8edf2;
      color: #1b2430;
    }
    .status {
      grid-column: 1 / 3;
      min-height: 20px;
      color: var(--muted);
    }
    .status.error { color: var(--danger); }
    .tabs {
      display: flex;
      gap: 6px;
      padding: 10px 10px 0;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }
    .tab {
      background: transparent;
      color: var(--muted);
      border-radius: 6px 6px 0 0;
      padding: 9px 10px;
    }
    .tab.active {
      color: var(--text);
      background: #fff;
      border: 1px solid var(--line);
      border-bottom-color: #fff;
      margin-bottom: -1px;
    }
    .table-wrap {
      overflow: auto;
      height: calc(100vh - 126px);
      padding: 12px;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      min-width: 720px;
      background: #fff;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      white-space: nowrap;
      vertical-align: top;
    }
    th {
      position: sticky;
      top: 0;
      background: #edf2f7;
      z-index: 1;
    }
    .formula {
      margin: 0 0 10px;
      color: var(--muted);
      line-height: 1.4;
    }
    @media (max-width: 860px) {
      main {
        grid-template-columns: 1fr;
        height: auto;
      }
      .table-wrap { height: 58vh; }
    }
  </style>
</head>
<body>
  <header><h1>Hardy Cross Moment Distribution</h1></header>
  <main>
    <section class="panel inputs">
      <div class="section">
        <h2>Beam Input</h2>
        <div class="grid">
          <div>
            <label for="supportCount">Number of supports</label>
            <input id="supportCount" type="number" min="2" max="30" value="3">
          </div>
          <div>
            <label for="maxCycles">Maximum cycles</label>
            <input id="maxCycles" type="number" min="1" value="50">
          </div>
          <div>
            <label for="tolerance">Tolerance</label>
            <input id="tolerance" type="text" value="0.0001">
          </div>
          <div>
            <label>&nbsp;</label>
            <label><input id="exteriorFixed" type="checkbox" checked> Exterior supports fixed</label>
          </div>
        </div>
      </div>
      <div class="span-list">
        <h2>Spans</h2>
        <p class="formula">Point loads use <strong>P@a</strong>, where <strong>a</strong> is the distance from the left support. Separate multiple point loads with semicolons.</p>
        <div id="spans"></div>
      </div>
      <div class="actions">
        <button class="primary" id="calculate">Calculate</button>
        <button class="secondary" id="clear">Clear Outputs</button>
        <div id="status" class="status">Enter span data, then calculate.</div>
      </div>
    </section>
    <section class="panel">
      <nav class="tabs" id="tabs"></nav>
      <div class="table-wrap" id="output"></div>
    </section>
  </main>
  <script>
    const supportCount = document.getElementById('supportCount');
    const spansEl = document.getElementById('spans');
    const statusEl = document.getElementById('status');
    const tabsEl = document.getElementById('tabs');
    const outputEl = document.getElementById('output');
    let currentResults = null;
    let activeTab = 'distribution';

    const tabLabels = {
      distribution: 'Distribution Factors',
      fem: 'Fixed-End Moment Calculations',
      moment: 'Moment Distribution',
      support: 'Final Support Moments'
    };

    function supportName(index) {
      const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
      return index < alphabet.length ? alphabet[index] : `S${index + 1}`;
    }

    function rebuildSpans() {
      const count = Number(supportCount.value);
      const old = new Map([...spansEl.querySelectorAll('.span-row')].map(row => [row.dataset.span, {
        length: row.querySelector('.length').value,
        udl: row.querySelector('.udl').value,
        pointLoads: row.querySelector('.point-loads').value
      }]));
      spansEl.innerHTML = '';
      if (!Number.isFinite(count) || count < 2) return;
      for (let i = 0; i < count - 1; i++) {
        const left = supportName(i);
        const right = supportName(i + 1);
        const name = `${left}${right}`;
        const previous = old.get(name) || { length: '', udl: '0', pointLoads: '' };
        const row = document.createElement('div');
        row.className = 'span-row';
        row.dataset.span = name;
        row.innerHTML = `
          <div class="span-name">${name}</div>
          <div>
            <label>Length L</label>
            <input class="length" type="text" value="${escapeAttr(previous.length)}">
          </div>
          <div>
            <label>UDL w</label>
            <input class="udl" type="text" value="${escapeAttr(previous.udl)}">
          </div>
          <div class="points">
            <label>Point loads</label>
            <input class="point-loads" type="text" placeholder="12@2; 8@4.5" value="${escapeAttr(previous.pointLoads)}">
          </div>
        `;
        spansEl.appendChild(row);
      }
    }

    function escapeAttr(value) {
      return String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    }

    function collectPayload() {
      const spans = [...spansEl.querySelectorAll('.span-row')].map(row => ({
        length: row.querySelector('.length').value,
        udl: row.querySelector('.udl').value,
        point_loads: row.querySelector('.point-loads').value
      }));
      return {
        support_count: supportCount.value,
        exterior_fixed: document.getElementById('exteriorFixed').checked,
        tolerance: document.getElementById('tolerance').value,
        max_cycles: document.getElementById('maxCycles').value,
        spans
      };
    }

    async function calculate() {
      setStatus('Calculating...', false);
      const response = await fetch('/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(collectPayload())
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(data.error || 'Calculation failed.', true);
        return;
      }
      currentResults = data;
      setStatus(data.status, false);
      renderTabs();
      renderActiveTable();
    }

    function setStatus(message, isError) {
      statusEl.textContent = message;
      statusEl.classList.toggle('error', Boolean(isError));
    }

    function renderTabs() {
      tabsEl.innerHTML = '';
      Object.entries(tabLabels).forEach(([key, label]) => {
        const button = document.createElement('button');
        button.className = `tab ${key === activeTab ? 'active' : ''}`;
        button.textContent = label;
        button.addEventListener('click', () => {
          activeTab = key;
          renderTabs();
          renderActiveTable();
        });
        tabsEl.appendChild(button);
      });
    }

    function renderActiveTable() {
      if (!currentResults) {
        outputEl.innerHTML = '<p class="formula">Results will appear here after calculation.</p>';
        return;
      }
      const table = currentResults.tables[activeTab];
      const note = activeTab === 'fem'
        ? '<p class="formula">Clockwise member-end moments are positive. UDL: left = -wL^2/12, right = wL^2/12. Point load: left = -Pab^2/L^2, right = Pa^2b/L^2, where b = L - a.</p>'
        : '';
      outputEl.innerHTML = note + buildTable(table.headers, table.rows);
    }

    function buildTable(headers, rows) {
      const head = headers.map(header => `<th>${escapeHtml(header)}</th>`).join('');
      const body = rows.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('');
      return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }

    function escapeHtml(value) {
      return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
    }

    document.getElementById('calculate').addEventListener('click', () => {
      calculate().catch(error => setStatus(error.message, true));
    });
    document.getElementById('clear').addEventListener('click', () => {
      currentResults = null;
      renderActiveTable();
      setStatus('Outputs cleared.', false);
    });
    supportCount.addEventListener('change', rebuildSpans);
    supportCount.addEventListener('input', rebuildSpans);
    rebuildSpans();
    renderTabs();
    renderActiveTable();
  </script>
</body>
</html>
"""


def parse_float(raw: object, label: str) -> float:
    try:
        return float(str(raw).strip())
    except ValueError as error:
        raise ValueError(f"{label} must be a number.") from error


def parse_point_loads(raw: object, length: float, span_name: str) -> List[Tuple[float, float]]:
    text = str(raw or "").strip()
    loads: List[Tuple[float, float]] = []
    if not text:
        return loads

    for part in text.split(";"):
        item = part.strip()
        if not item:
            continue
        if "@" not in item:
            raise ValueError(f"Point load '{item}' on span {span_name} must use P@a format.")
        load_text, distance_text = item.split("@", 1)
        load = parse_float(load_text, f"Point load magnitude on span {span_name}")
        distance = parse_float(distance_text, f"Point load distance on span {span_name}")
        if load < 0:
            raise ValueError(f"Point load magnitude on span {span_name} cannot be negative.")
        if distance < 0 or distance > length:
            raise ValueError(f"Point load distance on span {span_name} must be between 0 and {fmt(length)}.")
        loads.append((load, distance))
    return loads


def calculate_from_payload(payload: Dict[str, object]) -> Dict[str, object]:
    support_count = int(parse_float(payload.get("support_count", ""), "Number of supports"))
    if support_count < 2:
        raise ValueError("Number of supports must be at least 2.")

    tolerance = parse_float(payload.get("tolerance", "0.0001"), "Tolerance")
    max_cycles = int(parse_float(payload.get("max_cycles", "50"), "Maximum cycles"))
    if tolerance < 0:
        raise ValueError("Tolerance cannot be negative.")
    if max_cycles < 1:
        raise ValueError("Maximum cycles must be at least 1.")

    span_payloads = payload.get("spans", [])
    if not isinstance(span_payloads, list) or len(span_payloads) != support_count - 1:
        raise ValueError("The number of span input rows must be one less than the number of supports.")

    supports = support_names(support_count)
    spans: List[Span] = []
    for index, span_payload in enumerate(span_payloads):
        if not isinstance(span_payload, dict):
            raise ValueError("Each span input must be an object.")
        left = supports[index]
        right = supports[index + 1]
        span_name = f"{left}{right}"
        length = parse_float(span_payload.get("length", ""), f"Length for span {span_name}")
        if length <= 0:
            raise ValueError(f"Length for span {span_name} must be greater than 0.")
        udl = parse_float(span_payload.get("udl", "0") or "0", f"UDL for span {span_name}")
        if udl < 0:
            raise ValueError(f"UDL for span {span_name} cannot be negative.")
        point_loads = parse_point_loads(span_payload.get("point_loads", ""), length, span_name)
        spans.append(Span(left=left, right=right, length=length, udl=udl, point_loads=point_loads))

    fixed_supports = {supports[0], supports[-1]} if bool(payload.get("exterior_fixed", True)) else set()
    distribution_rows, distribution_factors, joint_ends, opposite = build_distribution_rows(
        spans,
        supports,
        fixed_supports,
    )
    md_headers, md_rows, final_moments, cycles_used = moment_distribution(
        spans,
        supports,
        fixed_supports,
        distribution_factors,
        joint_ends,
        opposite,
        tolerance,
        max_cycles,
    )

    return {
        "status": (
            f"Calculated {len(spans)} span(s) across {support_count} supports. "
            f"Moment distribution completed in {cycles_used} cycle(s)."
        ),
        "tables": {
            "distribution": {
                "headers": ["Joint", "Span", "Member end", "Relative stiffness 1/L", "Joint sum", "Distribution factor"],
                "rows": distribution_rows,
            },
            "fem": {
                "headers": ["Span", "Load", "End", "Formula", "Substitution", "Moment"],
                "rows": [row for span in spans for row in span.fixed_end_detail_rows()],
            },
            "moment": {"headers": md_headers, "rows": md_rows},
            "support": {
                "headers": ["Support", "Member-end moments", "Algebraic joint sum"],
                "rows": support_moment_rows(supports, joint_ends, final_moments),
            },
        },
    }


class MomentDistributionHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(APP_HTML.encode("utf-8"))

    def do_POST(self) -> None:
        if self.path != "/calculate":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = calculate_from_payload(payload)
            self.send_json(200, result)
        except (json.JSONDecodeError, ValueError) as error:
            self.send_json(400, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status_code: int, payload: Dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = "127.0.0.1"
    server = None
    port = 8000
    for candidate in range(8000, 8010):
        try:
            server = ThreadingHTTPServer((host, candidate), MomentDistributionHandler)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError("Could not start the GUI server on ports 8000 through 8009.")

    print("Hardy Cross Moment Distribution GUI")
    print(f"Open http://{host}:{port} in your browser.")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
