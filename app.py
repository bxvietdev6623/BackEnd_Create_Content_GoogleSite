# filename: app_direct_key.py

from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import json, re, time, os

# ========================================
# ⚙️ Cấu hình API - NẠP KHÓA TRỰC TIẾP
# ========================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ 缺少 OPENAI_API_KEY 环境变量，请在 Render 上设置 Environment Variables。")

# ✅ 使用 OpenRouter 代理（可换成官方 endpoint）
client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://openrouter.ai/api/v1")
MODEL = "gpt-4o-mini"

app = Flask(__name__)
CORS(app)

# ========================================
# 🔧 HÀM CÔNG CỤ
# ========================================
def call_chat(prompt, max_tokens=300, temperature=0.6, system_prompt=None):
    """Gọi mô hình OpenAI"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def generate_quality_keywords(base_kw, num_keywords):
    """
    Sinh ra danh sách từ khóa chính chất lượng cao (long-tail SEO keywords)
    dựa trên 1 từ khóa gốc.
    """
    prompt = (
        f"请基于关键词「{base_kw}」生成{num_keywords}个**高质量的中文长尾关键词**，"
        "这些关键词需比原关键词更具体，且更符合用户搜索意图或商业价值。\n"
        "例如，如果输入是“pg电子”，可生成：pg电子游戏攻略、pg电子注册指南、pg电子体验技巧等。\n"
        "只输出JSON数组格式，例如: [\"pg电子游戏攻略\",\"pg电子注册指南\",...]\n"
        "不要添加说明。"
    )
    text = call_chat(prompt, max_tokens=800, temperature=0.8)
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return [s.strip() for s in arr if s.strip()]
    except Exception:
        parts = re.split(r"[,\n;，；\s]+", text)
        return [p.strip() for p in parts if p.strip()]
    return []


def generate_related_keywords(main_kw):
    """Sinh 3 từ khóa phụ có liên quan trực tiếp đến từ khóa chính chất lượng cao"""
    prompt = (
        f"请为主关键词「{main_kw}」生成3个**高度相关的中文长尾关键词**。\n"
        "要求：\n"
        "1. 每个5~8个字；\n"
        "2. 紧密围绕主关键词主题；\n"
        "3. 不要与主关键词重复；\n"
        "4. 只输出JSON数组格式，例如: [\"词1\",\"词2\",\"词3\"]"
    )
    text = call_chat(prompt, max_tokens=200, temperature=0.8)
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return [s.strip() for s in arr if s.strip()][:3]
    except Exception:
        parts = re.split(r"[,\n;，；\s]+", text)
        return [p.strip() for p in parts if p.strip()][:3]
    return []


def generate_content(main_kw, related_kws, url, index):
    """Sinh bài viết với từ khóa chính chất lượng và 3 từ phụ"""
    related_str = "，".join(related_kws)
    system_prompt = "你是一位精通SEO的中文文案策划，请根据提供的关键词和URL生成一段自然的推广内容。"

    prompt = (
        f"请为主关键词「{main_kw}」写一段中文介绍：\n"
        f"这是第 {index+1} 篇文案，请确保与前面内容完全不同。\n"
        f"1. 必须以：{main_kw}【网址：{url}】开头；\n"
        f"2. Trong phần mô tả tiếp theo, hãy tự nhiên lồng ghép 2-3 từ khóa sau: {related_str}；\n"
        "3. Nội dung dài 100-150 từ, trôi chảy, hấp dẫn, không lặp từ khóa quá mức；\n"
        "4. Không xuống dòng, không thêm chú thích hoặc lời kết。"
    )
    text = call_chat(prompt, max_tokens=500, temperature=0.9, system_prompt=system_prompt)
    return " ".join(text.split())


# ========================================
# 🔥 API ROUTE
# ========================================
@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()

    if not data or "main_keyword" not in data or "num_articles" not in data:
        return jsonify({"error": "Thiếu tham số bắt buộc: main_keyword hoặc num_articles."}), 400

    base_kw = data["main_keyword"].strip()
    url = data.get("url", "http://191.run").strip()

    try:
        num_articles = int(data["num_articles"])
    except ValueError:
        return jsonify({"error": "num_articles phải là số nguyên."}), 400

    if not base_kw:
        return jsonify({"error": "Từ khóa chính không được để trống."}), 400

    if num_articles <= 0 or num_articles > 50:
        return jsonify({"error": "num_articles phải nằm trong khoảng 1–50."}), 400

    results = []

    # === Bước 1: Tạo N từ khóa chính chất lượng cao ===
    quality_keywords = generate_quality_keywords(base_kw, num_articles)
    if not quality_keywords:
        return jsonify({"error": "Không thể tạo danh sách từ khóa chính chất lượng cao."}), 500

    # === Bước 2: Với mỗi từ khóa chính chất lượng, tạo 3 từ phụ + nội dung ===
    for i, main_kw in enumerate(quality_keywords[:num_articles]):
        try:
            related_kws = generate_related_keywords(main_kw)
            content = generate_content(main_kw, related_kws, url, i)

            results.append({
                "base_keyword": base_kw,
                "main_kw_quality": main_kw,
                "related_keywords": related_kws,
                "content": content
            })

            time.sleep(0.5)

        except Exception as e:
            results.append({
                "main_kw_quality": main_kw,
                "error": f"Lỗi khi tạo bài {i+1}: {str(e)}"
            })
            time.sleep(0.5)

    return jsonify(results)


@app.route("/")
def home():
    return "✅ API nâng cấp: 1 từ khóa gốc → sinh nhiều từ khóa chính chất lượng + bài viết tương ứng."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
