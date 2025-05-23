from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse
import json
import datetime
from PIL import Image, ImageDraw, ImageFont
import io, requests
import random
import os
from dotenv import load_dotenv
import httpx
import secrets
from pymongo import MongoClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://Ego:MEME@meme.j5dfnh0.mongodb.net/?retryWrites=true&w=majority&appName=MEME")

client = MongoClient(MONGO_URL)
db = client["MEME"]         # Tên database của bạn
user_col = db["user"]       # Tên collection (giống như table trong SQL)

app = FastAPI()
USER_DATA_PATH = "user_data.json"
SHOP_DATA_PATH = "shop_data.json"

def get_user(user_id):
    return user_col.find_one({"_id": user_id})

def save_user(user_id, data):
    user_col.update_one({"_id": user_id}, {"$set": data}, upsert=True)

def calculate_level_and_progress(smart):
    level, need = 1, 50
    while smart >= need:
        smart -= need
        level += 1
        need = 50 + level * 45
    progress = smart / need if need > 0 else 1
    next_lv = smart + (need - smart)
    return level, progress, need

def get_role_name(level):
    if level < 3: return "Mẫu giáo"
    elif level < 6: return "Tiểu học (lớp 1)"
    elif level < 10: return "Trung học"
    elif level < 20: return "Cao đẳng"
    return "Tiến sĩ"
    
@app.get("/api/shop")
async def api_shop():
    shop_data = load_json(SHOP_DATA_PATH)
    return {"success": True, "shop": shop_data}

@app.get("/api/user/{user_id}")
async def api_get_user(user_id: str):
    user_data = load_json(USER_DATA_PATH)
    if user_id not in user_data:
        return {"success": False, "msg": "Không tìm thấy user"}
    data = user_data[user_id]
    return {
        "success": True,
        "points": data.get("points", 0),
        "items": data.get("items", {}),
        "smart": data.get("smart", 0)
    }

@app.get("/api/leaderboard/{kind}")
async def api_leaderboard(kind: str = "a"):
    user_data = load_json(USER_DATA_PATH)
    key = {"a": "points", "o": "company_balance", "s": "smart"}.get(kind, "points")
    users = [
        {"user_id": uid, "value": data.get(key, 0)}
        for uid, data in user_data.items() if isinstance(data, dict)
    ]
    users.sort(key=lambda x: x["value"], reverse=True)
    return {"success": True, "leaderboard": users}

@app.get("/api/jar")
async def api_jar():
    user_data = load_json(USER_DATA_PATH)
    jackpot_amount = user_data.get('jackpot', 0)
    # Định dạng số đẹp như bot:
    def format_currency(amount):
        return f"{amount:,.0f}".replace(",", " ")
    return {
        "success": True,
        "jackpot": jackpot_amount,
        "jackpot_fmt": format_currency(jackpot_amount)
    }

@app.get("/api/cccd/{user_id}")
async def api_cccd(
    request: Request,
    user_id: str,
    avatar: str = Query(default=None),
    username: str = Query(default=None),
    background: str = Query(default=None)
):
    user_data = load_json(USER_DATA_PATH)
    if user_id not in user_data:
        return {"success": False, "msg": "User không tồn tại!"}

    # ==== Load background galaxy ====
    try:
        if background:
            response = requests.get(background)
            bg = Image.open(io.BytesIO(response.content)).convert("RGBA").resize((400, 225))
        else:
            bg = Image.open("galaxy.png").convert("RGBA").resize((400, 225))  # Để galaxy.png trong thư mục app!
    except:
        bg = Image.new("RGBA", (400, 225), (30, 30, 70, 255))

    # 1. Ảnh nhỏ góc trái: luôn là 1.png
    avatar_small = Image.open("1.png").resize((64, 64)).convert("RGBA")

    # Bo tròn nếu muốn (optional)
    def circle_crop(img):
        size = img.size
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=255)
        out = Image.new('RGBA', size)
        out.paste(img, (0, 0), mask)
        return out

    avatar_small = circle_crop(avatar_small)  # Bỏ dòng này nếu không muốn bo tròn

    # Paste vào góc trái (toạ độ 10, 10)
    bg.paste(avatar_small, (10, 10), avatar_small)

    avatar_url = request.query_params.get('avatar', None)
    try:
        if avatar_url and avatar_url.startswith('http'):
            response = requests.get(avatar_url, timeout=3)
            avatar_big = Image.open(io.BytesIO(response.content)).resize((128, 128)).convert("RGBA")
        else:
            raise Exception("Không có avatar_url hợp lệ")
    except Exception as e:
        print("Lỗi avatar lớn:", e)
        avatar_big = Image.open("2.png").resize((128, 128)).convert("RGBA")

    bg.paste(avatar_big, (10, 65))

    # ==== Lấy dữ liệu user ====
    smart = user_data[user_id].get("smart", 0)
    level, progress, next_lv = calculate_level_and_progress(smart)  # Bạn cần thêm hàm này!
    role_name = get_role_name(level)  # Viết hàm này dựa vào level

    # ==== Font ====
    font_path = "Roboto-Black.ttf"
    try:
        font_big = ImageFont.truetype(font_path, 18)
        font_mid = ImageFont.truetype(font_path, 15)
        font_sm = ImageFont.truetype(font_path, 12)
    except:
        font_big = font_mid = font_sm = ImageFont.load_default()
    draw = ImageDraw.Draw(bg)

    # ==== Text tiêu đề ====
    draw.text((80, 10), "CỘNG HÒA XÃ HỘI CHỦ NGHĨA MEME", font=font_sm, fill="white")
    draw.text((102, 27), "Độc lập - Tự do - Hạnh phúc", font=font_sm, fill="white")
    draw.text((112, 47), "CĂN CƯỚC CƯ DÂN", font=font_big, fill="white")

    # ==== Text user info ====
    uname = username if username else user_id
    draw.text((150, 70), f"Tên: {uname}", font=font_mid, fill="white")
    draw.text((150, 92), f"ID: {user_id}", font=font_mid, fill="white")
    draw.text((150, 114), f"Học vấn: {smart}", font=font_mid, fill="white")
    draw.text((150, 136), f"lv: {level}", font=font_mid, fill="white")
    draw.text((150, 158), f"Trình độ: {role_name}", font=font_mid, fill="white")

    # ==== Thanh tiến độ level ====
    bar_x, bar_y, bar_w, bar_h = 150, 182, 200, 19
    draw.rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], outline="black", width=2)
    fill_w = int(bar_w * progress)
    draw.rectangle([bar_x+2, bar_y+2, bar_x+2+fill_w, bar_y+bar_h-2], fill="#1E90FF")
    draw.text((bar_x+5, bar_y+1), f"{smart}/{next_lv}", font=font_sm, fill="white")

    # ==== Xuất ảnh ====
    out = io.BytesIO()
    bg.save(out, format="PNG")
    out.seek(0)
    return StreamingResponse(out, media_type="image/png")

@app.get("/api/leaderboard/{kind}")
async def api_leaderboard(kind: str = "a"):
    user_data = load_json(USER_DATA_PATH)
    key = {"a": "points", "o": "company_balance", "s": "smart"}.get(kind, "points")
    users = [
        {"user_id": uid, "value": data.get(key, 0)}
        for uid, data in user_data.items() if isinstance(data, dict)
    ]
    users.sort(key=lambda x: x["value"], reverse=True)
    return {"success": True, "leaderboard": users}

@app.post("/api/start")
async def api_start(request: Request):
    data = await request.json()
    user_id = str(data["user_id"])
    user_data = load_json(USER_DATA_PATH)
    if user_id in user_data:
        return {"success": False, "msg": "Tài khoản đã tồn tại."}
    user_data[user_id] = {"points": 10000, "items": {}, "smart": 100}
    save_json(USER_DATA_PATH, user_data)
    return {"success": True, "msg": "Tạo tài khoản thành công!"}

@app.post("/api/buy")
async def api_buy(request: Request):
    data = await request.json()
    user_id = str(data["user_id"])
    item_id = data["item_id"]
    quantity = int(data["quantity"])
    user_data = load_json(USER_DATA_PATH)
    shop_data = load_json(SHOP_DATA_PATH)
    if user_id not in user_data:
        return {"success": False, "msg": "Bạn chưa có tài khoản!"}
    if item_id not in shop_data:
        return {"success": False, "msg": "Không tìm thấy sản phẩm!"}
    if quantity <= 0:
        return {"success": False, "msg": "Số lượng phải lớn hơn 0!"}
    total_price = shop_data[item_id]["price"] * quantity
    if total_price > user_data[user_id]["points"]:
        return {"success": False, "msg": "Bạn không đủ tiền!"}
    # Cập nhật
    user_data[user_id]["points"] -= total_price
    name = shop_data[item_id]["name"]
    user_items = user_data[user_id].setdefault("items", {})
    user_items[name] = user_items.get(name, 0) + quantity
    save_json(USER_DATA_PATH, user_data)
    return {"success": True, "msg": f"Bạn đã mua {quantity} {name}."}

@app.post("/api/sell")
async def api_sell(request: Request):
    data = await request.json()
    user_id = str(data["user_id"])
    item_id = data["item_id"]
    quantity = int(data["quantity"])
    user_data = load_json(USER_DATA_PATH)
    shop_data = load_json(SHOP_DATA_PATH)
    if user_id not in user_data:
        return {"success": False, "msg": "Bạn chưa có tài khoản!"}
    if item_id not in shop_data:
        return {"success": False, "msg": "Không tìm thấy sản phẩm trong cửa hàng!"}
    if quantity <= 0:
        return {"success": False, "msg": "Số lượng phải lớn hơn 0!"}

    item_name = shop_data[item_id]["name"]
    user_items = user_data[user_id].get("items", {})
    current_quantity = user_items.get(item_name, 0)
    if current_quantity < quantity:
        return {"success": False, "msg": "Bạn không có đủ vật phẩm để bán!"}

    selling_price = round(shop_data[item_id]["price"] * quantity * 0.9)
    user_items[item_name] -= quantity
    if user_items[item_name] == 0:
        del user_items[item_name]

    # Xóa company_balance nếu bán hết Công ty
    if item_id == "01" and "company_balance" in user_data[user_id]:
        if user_items.get(":office: Công ty", 0) == 0:
            del user_data[user_id]["company_balance"]

    user_data[user_id]["points"] += selling_price
    user_data[user_id]["items"] = user_items
    save_json(USER_DATA_PATH, user_data)
    return {
        "success": True,
        "msg": f"Bạn đã bán {quantity} {item_name} và nhận được {selling_price} coin!"
    }

@app.post("/api/sell")
async def api_sell(request: Request):
    data = await request.json()
    user_id = str(data["user_id"])
    item_id = data["item_id"]
    quantity = int(data["quantity"])
    user_data = load_json(USER_DATA_PATH)
    shop_data = load_json(SHOP_DATA_PATH)
    if user_id not in user_data:
        return {"success": False, "msg": "Bạn chưa có tài khoản!"}
    if item_id not in shop_data:
        return {"success": False, "msg": "Không tìm thấy sản phẩm!"}
    if quantity <= 0:
        return {"success": False, "msg": "Số lượng phải lớn hơn 0!"}
    item_name = shop_data[item_id]["name"]
    user_items = user_data[user_id].get("items", {})
    if user_items.get(item_name, 0) < quantity:
        return {"success": False, "msg": "Không đủ vật phẩm để bán!"}
    selling_price = round(shop_data[item_id]["price"] * quantity * 0.9)
    user_items[item_name] -= quantity
    user_data[user_id]["points"] += selling_price
    save_json(USER_DATA_PATH, user_data)
    return {"success": True, "msg": f"Bán thành công, nhận {selling_price} điểm!"}

@app.post("/api/daily")
async def api_daily(request: Request):
    data = await request.json()
    user_id = str(data["user_id"])
    user_data = load_json(USER_DATA_PATH)
    now = datetime.datetime.now()
    if user_id not in user_data:
        return {"success": False, "msg": "Bạn chưa có tài khoản!"}
    last_daily = user_data[user_id].get('last_daily')
    if last_daily is not None:
        last_daily_date = datetime.datetime.strptime(last_daily, "%Y-%m-%d")
        if last_daily_date.date() == now.date():
            return {"success": False, "msg": "Bạn đã nhận quà hằng ngày rồi. Vui lòng thử lại vào ngày mai."}
        elif (now - last_daily_date).days == 1:
            user_data[user_id]['streak'] = user_data[user_id].get('streak', 1) + 1
        else:
            user_data[user_id]['streak'] = 1
    else:
        user_data[user_id]['streak'] = 1
    base_reward = 5000
    streak_bonus = user_data[user_id]['streak'] * 100
    total_reward = base_reward + streak_bonus
    user_data[user_id]['points'] += total_reward
    user_data[user_id]['last_daily'] = now.strftime("%Y-%m-%d")
    save_json(USER_DATA_PATH, user_data)
    return {"success": True, "msg": f"Bạn đã nhận {total_reward} điểm! (Thưởng streak: {streak_bonus}, chuỗi ngày: {user_data[user_id]['streak']})"}

@app.post("/api/prog")
async def api_prog(request: Request):
    import random
    data = await request.json()
    user_id = str(data["user_id"])
    user_data = load_json(USER_DATA_PATH)
    now = datetime.datetime.now()
    if user_id not in user_data:
        return {"success": False, "msg": "Bạn chưa có tài khoản!"}
    last_beg = user_data[user_id].get('last_beg')
    if last_beg is not None:
        cooldown_time = 3 * 60
        time_elapsed = (now - datetime.datetime.strptime(last_beg, "%Y-%m-%d %H:%M:%S")).total_seconds()
        if time_elapsed < cooldown_time:
            minutes, seconds = divmod(int(cooldown_time - time_elapsed), 60)
            return {"success": False, "msg": f"Bạn đã ăn xin rồi, vui lòng thử lại sau {minutes} phút {seconds} giây."}
    if user_data[user_id]['points'] < 100000:
        beg_amount = random.randint(0, 5000)
        user_data[user_id]['points'] += beg_amount
    else:
        return {"success": False, "msg": 'Bạn quá giàu để ăn xin!'}
    user_data[user_id]['last_beg'] = now.strftime("%Y-%m-%d %H:%M:%S")
    save_json(USER_DATA_PATH, user_data)
    return {"success": True, "msg": f"Bạn đã nhận được {beg_amount} điểm từ việc ăn xin!"}

@app.post("/api/ou")
async def api_ou(request: Request):
    data = await request.json()
    user_id = str(data["user_id"])
    bet = data["bet"]
    choice = data["choice"].lower()
    user_data = load_json(USER_DATA_PATH)
    if user_id not in user_data:
        return {"success": False, "msg": "Bạn chưa có tài khoản!"}
    if isinstance(bet, str) and bet.lower() == 'all':
        bet = user_data[user_id]['points']
    try:
        bet = int(bet)
    except Exception:
        return {"success": False, "msg": "Số điểm cược không hợp lệ!"}
    if bet <= 0 or bet > user_data[user_id]['points']:
        return {"success": False, "msg": "Bạn không đủ tiền để cược!"}
    if choice not in ["t", "x"]:
        return {"success": False, "msg": "Bạn phải chọn 't' (Tài) hoặc 'x' (Xỉu)!"}
    # Xử lý đặc biệt cho admin (bạn có thể bỏ)
    if user_id == "1361702060071850024":
        dice = [random.randint(1,3) for _ in range(3)]
    else:
        dice = [random.randint(1,6) for _ in range(3)]
    total = sum(dice)
    win = False
    if (3 <= total <= 10 and choice == "x") or (11 <= total <= 18 and choice == "t"):
        user_data[user_id]['points'] += bet
        win = True
    else:
        user_data[user_id]['points'] -= bet
    save_json(USER_DATA_PATH, user_data)
    return {
        "success": True,
        "win": win,
        "total": total,
        "dice": dice,
        "bet": bet,
        "choice": choice,
        "msg": f"{'Thắng' if win else 'Thua'}! Tổng điểm: {total} ({'Xỉu' if total<=10 else 'Tài'}) - {'Bạn chọn Xỉu' if choice=='x' else 'Bạn chọn Tài'}. {'+ ' if win else '- '}{bet} coin!"
    }

@app.post("/api/hunt")
async def api_hunt(request: Request):
    data = await request.json()
    user_id = str(data["user_id"])
    weapon = data["weapon"]  # "g", "r", "a", "c"
    user_data = load_json(USER_DATA_PATH)

    # Dữ liệu vũ khí giống trong bot
    weapon_data = {
        "g": {"item": ":gun: Súng săn", "ammo": 1, "reward_range": (0, 50000)},
        "r": {"item": "<:RPG:1325750069189677087> RPG", "ammo": 10, "reward_range": (-2000000, 5000000)},
        "a": {"item": "<:Awm:1325747265045794857> Awm", "ammo": 1, "reward_range": (5000, 1000000)},
        "c": {"item": "<:cleaner:1347560866291257385> máy hút bụi", "ammo": 0, "reward_range": (3000000, 10000000)}
    }

    if user_id not in user_data:
        return {"success": False, "msg": "Bạn chưa có tài khoản!"}
    if weapon not in weapon_data:
        return {"success": False, "msg": "Vũ khí không hợp lệ!"}

    now = datetime.datetime.now()
    last_hunt = user_data[user_id].get('last_hunt')
    cooldown_time = 5 * 60
    if last_hunt:
        time_elapsed = (now - datetime.datetime.strptime(last_hunt, "%Y-%m-%d %H:%M:%S")).total_seconds()
        if time_elapsed < cooldown_time:
            minutes, seconds = divmod(int(cooldown_time - time_elapsed), 60)
            return {"success": False, "msg": f"Bạn cần chờ {minutes} phút {seconds} giây trước khi săn tiếp!"}

    weapon_info = weapon_data[weapon]
    user_items = user_data[user_id].get('items', {})
    weapon_count = user_items.get(weapon_info["item"], 0)
    ammo_count = user_items.get(":bullettrain_side: Viên đạn", 0)

    if weapon_count < 1:
        return {"success": False, "msg": f"Bạn cần có {weapon_info['item']} để đi săn!"}
    if ammo_count < weapon_info["ammo"]:
        return {"success": False, "msg": f"Bạn cần có {weapon_info['ammo']} viên đạn để đi săn!"}

    # Nếu dùng máy hút bụi thì xóa luôn khỏi kho
    if weapon == "c":
        del user_data[user_id]['items'][weapon_info["item"]]
    # Trừ đạn
    user_data[user_id]['items'][":bullettrain_side: Viên đạn"] -= weapon_info["ammo"]
    if user_data[user_id]['items'][":bullettrain_side: Viên đạn"] == 0:
        del user_data[user_id]['items'][":bullettrain_side: Viên đạn"]

    # Tính phần thưởng
    hunt_reward = random.randint(*weapon_info["reward_range"])
    user_data[user_id]['points'] += hunt_reward
    user_data[user_id]['last_hunt'] = now.strftime("%Y-%m-%d %H:%M:%S")

    save_json(USER_DATA_PATH, user_data)
    return {
        "success": True,
        "msg": f"Bạn đã săn thành công và kiếm được {hunt_reward} coin!",
        "reward": hunt_reward,
        "weapon": weapon_info["item"]
    }

@app.post("/api/study")
async def api_study(request: Request):
    data = await request.json()
    user_id = str(data["user_id"])
    user_data = load_json(USER_DATA_PATH)
    now = datetime.datetime.now()
    if user_id not in user_data:
        return {"success": False, "msg": "Bạn chưa có tài khoản!"}
    last_study = user_data[user_id].get('last_study')
    cooldown_time = 5 * 60  # 5 phút
    if last_study is not None:
        time_elapsed = (now - datetime.datetime.strptime(last_study, "%Y-%m-%d %H:%M:%S")).total_seconds()
        if time_elapsed < cooldown_time:
            minutes, seconds = divmod(int(cooldown_time - time_elapsed), 60)
            return {"success": False, "msg": f"Bạn cần chờ {minutes} phút {seconds} giây trước khi có thể học tiếp!"}
    user_data[user_id]['smart'] = user_data[user_id].get('smart', 0) + 10
    user_data[user_id]['last_study'] = now.strftime("%Y-%m-%d %H:%M:%S")
    save_json(USER_DATA_PATH, user_data)
    return {"success": True, "msg": "Bạn vừa học xong ra chơi thôi!", "smart": user_data[user_id]['smart']}

load_dotenv()


# Các biến sau điền đúng info app Discord của bạn!
CLIENT_ID = "1362314957714231326"
CLIENT_SECRET = "C3WiceqvHAFQ3FQ7-mH6oFZbt2pYSVxC"
REDIRECT_URI = "https://meme-xaph.onrender.com/auth/discord/callback"  # hoặc domain thật nếu deploy

# Route đăng nhập
@app.get("/login/discord")
def login_discord():
    discord_oauth_url = (
        f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify"
    )
    return RedirectResponse(discord_oauth_url)

# Route callback
@app.get("/auth/discord/callback")
async def discord_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return HTMLResponse("Lỗi xác thực Discord.", status_code=400)

    # Lấy access token
    token_url = "https://discord.com/api/oauth2/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=data, headers=headers)
        if token_response.status_code != 200:
            return HTMLResponse("Không lấy được token Discord.", status_code=400)
        tokens = token_response.json()
        access_token = tokens.get("access_token")

        # Lấy user info từ Discord API
        user_response = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user = user_response.json()
        discord_id = user["id"]
        username = user["username"]
        avatar = f'https://cdn.discordapp.com/avatars/{discord_id}/{user["avatar"]}.png'
        # Token hóa session: bạn có thể sinh JWT/Set Cookie... ở đây demo trả về user info luôn
        content = f"""
        <h1>Đăng nhập thành công!</h1>
        <img src="{avatar}" width=80><br>
        Xin chào <b>{username}</b>!<br>
        Discord ID: <code>{discord_id}</code><br>
        <script>
          localStorage.setItem('uid', '{discord_id}');
          localStorage.setItem('avatar', '{avatar}');
          localStorage.setItem('username', '{username}');
          window.location = '/';  // chuyển về trang chính hoặc dashboard
        </script>
        """
        return HTMLResponse(content)

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)   
