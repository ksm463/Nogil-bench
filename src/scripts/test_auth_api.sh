#!/bin/bash
# JWT 인증 API 수동 테스트 스크립트
# 사용법: bash src/scripts/test_auth_api.sh [BASE_URL]

BASE=${1:-http://localhost:8000}
PASS=0
FAIL=0

# 색상
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

echo -e "${BOLD}=== Auth API 테스트 ===${NC}"
echo "Base URL: $BASE"
echo ""

# --- 1. 회원가입 ---
echo -e "${BOLD}[회원가입]${NC}"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"auth_test@example.com","password":"testpass123"}')
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "신규 가입 → 201" 201 "$CODE" "$BODY"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"auth_test@example.com","password":"other"}')
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "중복 이메일 → 409" 409 "$CODE" "$BODY"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"not-an-email","password":"testpass123"}')
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "잘못된 이메일 형식 → 422" 422 "$CODE" "$BODY"

echo ""

# --- 2. 로그인 ---
echo -e "${BOLD}[로그인]${NC}"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
    -d "username=auth_test@example.com&password=testpass123")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "정상 로그인 → 200" 200 "$CODE" "$BODY"

TOKEN=$(echo "$BODY" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
    -d "username=auth_test@example.com&password=wrongpassword")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "잘못된 패스워드 → 401" 401 "$CODE" "$BODY"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
    -d "username=nobody@example.com&password=testpass123")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "존재하지 않는 이메일 → 401" 401 "$CODE" "$BODY"

echo ""

# --- 3. /auth/me ---
echo -e "${BOLD}[내 정보 조회]${NC}"

RESP=$(curl -s -w "\n%{http_code}" "$BASE/auth/me" \
    -H "Authorization: Bearer $TOKEN")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "유효한 토큰 → 200" 200 "$CODE" "$BODY"

RESP=$(curl -s -w "\n%{http_code}" "$BASE/auth/me")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "토큰 없이 → 401" 401 "$CODE" "$BODY"

RESP=$(curl -s -w "\n%{http_code}" "$BASE/auth/me" \
    -H "Authorization: Bearer invalid.token.here")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_status "잘못된 토큰 → 401" 401 "$CODE" "$BODY"

echo ""

# --- 정리 ---
echo -e "${BOLD}=== 결과: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC} ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
