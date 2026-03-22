"""
Product Radar - 웹 대시보드
브라우저에서 상품 확인 + 링크 클릭 가능

실행:
    python app.py
그 다음 브라우저에서: http://localhost:5000
"""

import json
import threading
import time
from datetime import datetime
from queue import Queue

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from config import config, FAST_SHIP_CATEGORIES
from storage.database import init_db
from main import run_radar_scan

app = Flask(__name__)

# 스캔 상태 관리
_scan_lock = threading.Lock()
_scan_running = False
_last_results = []
_last_scan_time = None
_progress_queue = Queue()


def _run_scan_background(categories=None, export=False):
    """백그라운드 스캔 실행"""
    global _scan_running, _last_results, _last_scan_time

    try:
        _progress_queue.put({"type": "start", "message": "스캔 시작..."})
        results = run_radar_scan(categories=categories, export=export, top_n=20)
        _last_results = results
        _last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _progress_queue.put({
            "type": "done",
            "message": f"완료! {len(results)}개 상품 발견",
            "count": len(results),
        })
    except Exception as e:
        _progress_queue.put({"type": "error", "message": f"오류: {e}"})
    finally:
        with _scan_lock:
            global _scan_running
            _scan_running = False


@app.route("/")
def index():
    return render_template(
        "index.html",
        products=_last_results,
        scan_time=_last_scan_time,
        scanning=_scan_running,
        categories=list(FAST_SHIP_CATEGORIES.keys()),
    )


@app.route("/scan", methods=["POST"])
def start_scan():
    global _scan_running

    with _scan_lock:
        if _scan_running:
            return jsonify({"ok": False, "message": "이미 스캔 중입니다"})
        _scan_running = True

    # 큐 비우기
    while not _progress_queue.empty():
        _progress_queue.get_nowait()

    cats = request.json.get("categories") if request.is_json else None
    export = request.json.get("export", False) if request.is_json else False

    t = threading.Thread(
        target=_run_scan_background,
        args=(cats or None, export),
        daemon=True,
    )
    t.start()
    return jsonify({"ok": True, "message": "스캔 시작됨"})


@app.route("/progress")
def progress():
    """SSE: 스캔 진행 상황 실시간 스트리밍"""
    def generate():
        while True:
            if not _progress_queue.empty():
                msg = _progress_queue.get()
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg["type"] in ("done", "error"):
                    break
            else:
                if not _scan_running:
                    break
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                time.sleep(0.5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/products")
def api_products():
    """JSON API: 현재 스캔 결과"""
    return jsonify({
        "count": len(_last_results),
        "scan_time": _last_scan_time,
        "products": [_format_product(p) for p in _last_results],
    })


@app.route("/status")
def status():
    return jsonify({
        "scanning": _scan_running,
        "count": len(_last_results),
        "scan_time": _last_scan_time,
    })


def _format_product(item: dict) -> dict:
    """템플릿용 상품 데이터 정제"""
    p = item.get("product", {})
    s = item.get("scores", {})
    pricing = s.get("pricing", {})
    commercial = s.get("commercial", {})

    return {
        "product_id": p.get("product_id", ""),
        "title": p.get("title", "")[:80],
        "category": p.get("category", ""),
        "image_url": p.get("image_url", ""),
        "product_url": p.get("product_url", "#"),
        "supplier": p.get("supplier", ""),
        "rating": round(p.get("rating", 0), 1),
        "review_count": p.get("review_count", 0),
        "shipping_days": p.get("shipping_days", 0),
        "cost_usd": round(p.get("cost_usd", 0), 2),
        "sell_price": round(pricing.get("sell_price", 0) or commercial.get("optimal_sell_price", 0), 2),
        "margin_pct": round(commercial.get("margin_pct", 0), 1),
        "total_score": round(s.get("total_score", 0), 1),
        "viral_score": round(s.get("viral_score", 0), 1),
        "trend_score": round(s.get("trend_score", 0), 1),
        "profit_score": round(s.get("profit_score", 0), 1),
        "quality_score": round(s.get("quality_score", 0), 1),
        "shipping_score": round(s.get("shipping_score", 0), 1),
        "viral_grade": s.get("viral_grade", "C"),
        "is_24h_spike": s.get("is_24h_spike", False),
        "is_3d_repeat": s.get("is_3d_repeat", False),
    }


if __name__ == "__main__":
    init_db()
    print("\n" + "="*50)
    print("  Product Radar 웹 대시보드 시작!")
    print("  브라우저 주소창에 입력: http://localhost:5000")
    print("="*50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=5000)
