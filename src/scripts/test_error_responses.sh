#!/bin/bash
# 커스텀 에러 응답 형식 검증 스크립트
# Day 4: 모든 에러가 {"error_code": "...", "message": "..."} 형식인지 확인
# 사용법: bash src/scripts/test_error_responses.sh [BASE_URL]

BASE=${1:-http://localhost:8000}
PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

assert_error_response() {
    local test_name=$1
    local expected_code=$2
    local expected_error_code=$3
    local actual_code=$4
    local body=$5

    # HTTP 상태코드 검증
    if [ "$actual_code" -ne "$expected_code" ]; then
        echo -e "  ${RED}FAIL${NC} $test_name — HTTP $actual_code (expected $expected_code)"
        echo "       $body"
        ((FAIL++))
        return
    fi

    # error_code 필드 존재 여부 검증
    local actual_error_code
    actual_error_code=$(echo "$body" | python3 -c "import sys,json;print(json.load(sys.stdin).get('error_code',''))" 2>/dev/null)

    if [ "$actual_error_code" != "$expected_error_code" ]; then
        echo -e "  ${RED}FAIL${NC} $test_name — error_code='$actual_error_code' (expected '$expected_error_code')"
        echo "       $body"
        ((FAIL++))
        return
    fi

    # message 필드 존재 여부 검증
    local has_message
    has_message=$(echo "$body" | python3 -c "import sys,json;d=json.load(sys.stdin);print('yes' if 'message' in d and d['message'] else 'no')" 2>/dev/null)

    if [ "$has_message" != "yes" ]; then
        echo -e "  ${RED}FAIL${NC} $test_name — message 필드 없음"
        echo "       $body"
        ((FAIL++))
        return
    fi

    echo -e "  ${GREEN}PASS${NC} $test_name (HTTP $actual_code, $actual_error_code)"
    ((PASS++))
}

echo -e "${BOLD}=== 커스텀 에러 응답 형식 검증 ===${NC}"
echo "Base URL: $BASE"
echo ""

# --- 준비: 테스트용 유저 생성 ---
curl -s -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"errtest@example.com","password":"test1234"}' > /dev/null

TOKEN=$(curl -s -X POST "$BASE/auth/login" \
    -d "username=errtest@example.com&password=test1234" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Alice 이미지 업로드 (Bob의 403 테스트용)
curl -s -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"err_alice@example.com","password":"alice123"}' > /dev/null

TOKEN_ALICE=$(curl -s -X POST "$BASE/auth/login" \
    -d "username=err_alice@example.com&password=alice123" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

TMPIMG=$(mktemp /tmp/test_XXXXXX.png)
python3 -c "from PIL import Image; Image.new('RGB',(100,100),'red').save('$TMPIMG')" 2>/dev/null

UPLOAD_RESP=$(curl -s -X POST "$BASE/api/images/upload" \
    -H "Authorization: Bearer $TOKEN_ALICE" \
    -F "file=@$TMPIMG")
ALICE_IMG_ID=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])" 2>/dev/null)

echo -e "${BOLD}[409 DUPLICATE_EMAIL]${NC}"
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"errtest@example.com","password":"other"}')
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_error_response "중복 이메일 가입" 409 "DUPLICATE_EMAIL" "$CODE" "$BODY"
echo ""

echo -e "${BOLD}[401 INVALID_CREDENTIALS]${NC}"
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
    -d "username=errtest@example.com&password=wrongpass")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_error_response "잘못된 패스워드 로그인" 401 "INVALID_CREDENTIALS" "$CODE" "$BODY"

RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/auth/login" \
    -d "username=nobody@example.com&password=test1234")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_error_response "존재하지 않는 이메일 로그인" 401 "INVALID_CREDENTIALS" "$CODE" "$BODY"
echo ""

echo -e "${BOLD}[401 INVALID_TOKEN]${NC}"
RESP=$(curl -s -w "\n%{http_code}" "$BASE/auth/me" \
    -H "Authorization: Bearer invalid.token.here")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_error_response "잘못된 토큰으로 /me 접근" 401 "INVALID_TOKEN" "$CODE" "$BODY"
echo ""

echo -e "${BOLD}[404 IMAGE_NOT_FOUND]${NC}"
RESP=$(curl -s -w "\n%{http_code}" "$BASE/api/images/99999" \
    -H "Authorization: Bearer $TOKEN")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_error_response "존재하지 않는 이미지 조회" 404 "IMAGE_NOT_FOUND" "$CODE" "$BODY"
echo ""

echo -e "${BOLD}[403 FORBIDDEN]${NC}"
RESP=$(curl -s -w "\n%{http_code}" "$BASE/api/images/$ALICE_IMG_ID" \
    -H "Authorization: Bearer $TOKEN")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_error_response "타인 이미지 조회" 403 "FORBIDDEN" "$CODE" "$BODY"
echo ""

echo -e "${BOLD}[400 INVALID_OPERATION]${NC}"
RESP=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/images/$ALICE_IMG_ID/process" \
    -H "Authorization: Bearer $TOKEN_ALICE" \
    -H "Content-Type: application/json" \
    -d '{"operation":"nonexistent_op"}')
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_error_response "지원하지 않는 이미지 작업" 400 "INVALID_OPERATION" "$CODE" "$BODY"
echo ""

echo -e "${BOLD}[400 IMAGE_NOT_PROCESSED]${NC}"
RESP=$(curl -s -w "\n%{http_code}" "$BASE/api/images/$ALICE_IMG_ID/download" \
    -H "Authorization: Bearer $TOKEN_ALICE")
BODY=$(echo "$RESP" | head -1)
CODE=$(echo "$RESP" | tail -1)
assert_error_response "미처리 이미지 다운로드" 400 "IMAGE_NOT_PROCESSED" "$CODE" "$BODY"
echo ""

# --- 정리 ---
rm -f "$TMPIMG"
echo -e "${BOLD}=== 결과: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC} ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
