#!/bin/bash
# 이미지 API + 인증 통합 테스트 스크립트
# 사용법: bash src/scripts/test_image_auth_api.sh [BASE_URL]

BASE=${1:-http://localhost:8000}
PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

assert_status() {
    local test_name=$1 expected=$2 actual=$3 body=$4
    if [ "$actual" -eq "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC} $test_name (HTTP $actual)"
        ((PASS++))
    else
        echo -e "  ${RED}FAIL${NC} $test_name — expected $expected, got $actual"
        echo "       $body"
        ((FAIL++))
    fi
}

# --- 사전 준비: 유저 2명 생성 + 로그인 ---
echo -e "${BOLD}=== 이미지 API + 인증 통합 테스트 ===${NC}"
echo ""

echo -e "${BOLD}[준비] 유저 2명 생성${NC}"
curl -s -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"alice@test.com","password":"alice123"}' > /dev/null

curl -s -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"bob@test.com","password":"bob123"}' > /dev/null

TOKEN_A=$(curl -s -X POST "$BASE/auth/login" \
    -d "username=alice@test.com&password=alice123" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

TOKEN_B=$(curl -s -X POST "$BASE/auth/login" \
    -d "username=bob@test.com&password=bob123" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

echo "  Alice 토큰: ${TOKEN_A:0:20}..."
echo "  Bob   토큰: ${TOKEN_B:0:20}..."
echo ""

# --- 1. 토큰 없이 접근 → 401 ---
echo -e "${BOLD}[인증 필수 확인]${NC}"

RESP=$(curl -s -w "\n%{http_code}" "$BASE/api/images/")
CODE=$(echo "$RESP" | tail -1)
assert_status "토큰 없이 목록 조회 → 401" 401 "$CODE"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/images/upload" -F "file=@/dev/null")
CODE=$(echo "$RESP" | tail -1)
assert_status "토큰 없이 업로드 → 401" 401 "$CODE"

echo ""

# --- 2. Alice 이미지 업로드 ---
echo -e "${BOLD}[Alice 이미지 업로드]${NC}"

# 테스트용 이미지 생성 (1x1 PNG)
TMPIMG=$(mktemp /tmp/test_XXXXXX.png)
python3 -c "
from PIL import Image
Image.new('RGB',(100,100),'red').save('$TMPIMG')
" 2>/dev/null || {
    # PIL 없으면 최소 PNG 바이너리로 생성
    printf '\x89PNG\r\n\x1a\n' > "$TMPIMG"
}

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/images/upload" \
    -H "Authorization: Bearer $TOKEN_A" \
    -F "file=@$TMPIMG")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "Alice 업로드 → 200" 200 "$CODE"

IMAGE_ID=$(echo "$BODY" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])" 2>/dev/null)
echo "  업로드된 이미지 ID: $IMAGE_ID"
echo ""

# --- 3. Alice 본인 이미지 접근 → 200 ---
echo -e "${BOLD}[소유자 접근]${NC}"

RESP=$(curl -s -w "\n%{http_code}" "$BASE/api/images/$IMAGE_ID" \
    -H "Authorization: Bearer $TOKEN_A")
CODE=$(echo "$RESP" | tail -1)
assert_status "Alice가 본인 이미지 조회 → 200" 200 "$CODE"

RESP=$(curl -s -w "\n%{http_code}" "$BASE/api/images/" \
    -H "Authorization: Bearer $TOKEN_A")
CODE=$(echo "$RESP" | tail -1)
assert_status "Alice 목록 조회 → 200" 200 "$CODE"

echo ""

# --- 4. Bob이 Alice 이미지 접근 → 403 ---
echo -e "${BOLD}[타인 이미지 접근 차단]${NC}"

RESP=$(curl -s -w "\n%{http_code}" "$BASE/api/images/$IMAGE_ID" \
    -H "Authorization: Bearer $TOKEN_B")
CODE=$(echo "$RESP" | tail -1)
assert_status "Bob이 Alice 이미지 조회 → 403" 403 "$CODE"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/images/$IMAGE_ID/process" \
    -H "Authorization: Bearer $TOKEN_B" \
    -H "Content-Type: application/json" \
    -d '{"operation":"blur"}')
CODE=$(echo "$RESP" | tail -1)
assert_status "Bob이 Alice 이미지 처리 → 403" 403 "$CODE"

RESP=$(curl -s -w "\n%{http_code}" -X DELETE "$BASE/api/images/$IMAGE_ID" \
    -H "Authorization: Bearer $TOKEN_B")
CODE=$(echo "$RESP" | tail -1)
assert_status "Bob이 Alice 이미지 삭제 → 403" 403 "$CODE"

echo ""

# --- 5. Bob 목록은 비어있어야 함 ---
echo -e "${BOLD}[사용자별 격리]${NC}"

RESP=$(curl -s "$BASE/api/images/" -H "Authorization: Bearer $TOKEN_B")
COUNT=$(echo "$RESP" | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null)
if [ "$COUNT" = "0" ]; then
    echo -e "  ${GREEN}PASS${NC} Bob 목록 비어있음 (${COUNT}건)"
    ((PASS++))
else
    echo -e "  ${RED}FAIL${NC} Bob 목록에 ${COUNT}건 (0건이어야 함)"
    ((FAIL++))
fi

echo ""

# --- 6. Alice 이미지 삭제 ---
echo -e "${BOLD}[소유자 삭제]${NC}"

RESP=$(curl -s -w "\n%{http_code}" -X DELETE "$BASE/api/images/$IMAGE_ID" \
    -H "Authorization: Bearer $TOKEN_A")
CODE=$(echo "$RESP" | tail -1)
assert_status "Alice가 본인 이미지 삭제 → 200" 200 "$CODE"

echo ""

# --- 정리 ---
rm -f "$TMPIMG"
echo -e "${BOLD}=== 결과: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC} ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
