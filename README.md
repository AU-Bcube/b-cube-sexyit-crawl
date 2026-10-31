# b-cube-sexyit-crawl

공개 Instagram 계정의 게시물을 매일 크롤링해 이미지는 Cloudflare R2에, 게시물 정보는 MongoDB `sexyits2` 컬렉션에 저장합니다. Instagram 로그인 없이 동작합니다.

## 동작 방식

매일 08:00(KST)에 GitHub Actions에서 실행됩니다.

1. MongoDB `sexyits2`에 저장된 `ig_post_id` 목록을 읽습니다.
2. 대상 계정의 게시물을 첫 페이지부터 마지막 페이지까지 모두 가져옵니다.
3. 저장된 목록과 비교합니다.
   - **새 게시물:** 가장 큰 해상도의 이미지를 R2에 올리고 MongoDB에 저장합니다. 여러 장짜리 게시물은 첫 장, 동영상은 커버 이미지를 씁니다.
   - **본문에 해시태그가 없는 새 게시물:** 저장하지 않고 건너뜁니다. 나중에 해시태그가 추가되면 다음 실행에서 저장됩니다.
   - **Instagram에서 삭제된 게시물:** MongoDB에서만 지웁니다. R2 이미지는 남겨둡니다.

## 저장 스키마 (`sexyits2`)

| 필드 | 내용 |
|---|---|
| `date` | 게시물 업로드 시각 (UTC) |
| `title` | 본문에서 처음 나오는 해시태그 (`#` 제외) |
| `imagePath` | R2 공개 URL. `$S3_DEV_ACCESS_URL/<S3_PREFIX>/<shortcode>.<ext>` |
| `url` | `https://www.instagram.com/p/<shortcode>/` |
| `ig_post_id` | 게시물 shortcode (고유 인덱스) |

## 로컬 실행

[uv](https://docs.astral.sh/uv/)가 필요합니다. Python 버전은 `.python-version`(3.12)을 따릅니다.

```bash
uv sync
cp .env.example .env   # 값 채우기
uv run --env-file .env python -m crawler
uv run pytest          # 단위 테스트
```

> 로컬에서 실행해도 실제 R2와 MongoDB에 저장됩니다.

## 환경변수

| 이름 | 필수 | 설명 |
|---|---|---|
| `IG_USERNAME` | ✓ | 크롤링할 Instagram 계정 (공개 계정이어야 함) |
| `DB_CONNECTION_STRING` | ✓ | MongoDB 연결 문자열 |
| `DB_NAME` | ✓ | MongoDB DB 이름 |
| `S3_ENDPOINT` | ✓ | `https://<account-id>.r2.cloudflarestorage.com/<bucket>` 형태. 경로 부분을 버킷 이름으로 사용 |
| `S3_PREFIX` | ✓ | R2 객체 키 접두사. 예: `/sexyit2/` |
| `S3_ACCESS_KEY_ID` | ✓ | R2 API 토큰 액세스 키 |
| `S3_SECRET_ACCESS_KEY` | ✓ | R2 API 토큰 시크릿 키 |
| `S3_DEV_ACCESS_URL` | ✓ | R2 공개 URL. 예: `https://pub-xxxx.r2.dev` |
| `MAX_DELETE_RATIO` | | 한 번에 삭제할 수 있는 최대 비율. 기본값 `0.5` |

## GitHub Actions 설정

워크플로: [.github/workflows/crawl.yml](.github/workflows/crawl.yml)

저장소의 **Settings → Secrets and variables → Actions**에 아래 값을 등록합니다.

- **Secrets:** `DB_CONNECTION_STRING`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`
- **Variables:** `IG_USERNAME`, `DB_NAME`, `S3_ENDPOINT`, `S3_PREFIX`, `S3_DEV_ACCESS_URL`, `MAX_DELETE_RATIO`(선택)

**Actions → Crawl Instagram → Run workflow**로 수동 실행할 수도 있습니다. GitHub 예약 실행은 몇 분에서 수십 분 늦게 시작될 수 있습니다.

## 안전장치

크롤링이 막히거나 일부만 성공했을 때 DB가 잘못 비워지지 않게 하는 장치입니다. 아래 경우에는 아무것도 삭제하지 않고 실패로 끝납니다.

- 수집한 게시물 수가 프로필의 총 게시물 수보다 적을 때
- 페이지를 넘겨도 새 게시물이 나오지 않을 때 (커서가 무시되는 경우)
- 수집 결과가 0건일 때
- 삭제 대상이 3건 이상이면서 저장된 게시물의 `MAX_DELETE_RATIO`를 넘을 때

게시물 하나의 저장이 실패해도 나머지는 계속 처리하고, 마지막에 종료 코드 1로 실패를 알립니다. 다음 실행에서 다시 시도하며, 같은 게시물이 중복 저장되지 않습니다.

## 구조

```
crawler/
  __main__.py   실행 진입점: 비교 → R2 업로드 → MongoDB 저장/삭제
  instagram.py  로그인 없는 전체 게시물 수집 (instagrapi)
  post.py       Instagram 미디어 → Post 변환, 해시태그·이미지 추출
  sync.py       저장된 목록과 수집 결과 비교, 안전장치
  r2.py         이미지 다운로드 및 R2 업로드
  config.py     환경변수 로드·검증
tests/          단위 테스트
docs/DESIGN.md  설계 문서
```

## 알려진 제약

- **비공식 API 사용:** [instagrapi](https://github.com/subzeroid/instagrapi)의 내부 메서드와 Instagram 비공식 쿼리에 의존합니다. 로그인 없이는 instagrapi가 다음 페이지를 넘기지 못해서, `crawler/instagram.py`의 `TimelineClient`가 페이지 커서를 `profile_grid_items_cursor` 변수로 바꿔 보냅니다. instagrapi나 Instagram이 바뀌면 동작하지 않을 수 있습니다. 그럴 때는 위 안전장치 때문에 실행이 실패로 끝나고 데이터는 바뀌지 않습니다.
- **IP 차단:** Instagram이 데이터센터 IP의 로그인 없는 요청을 막을 수 있습니다. GitHub Actions에서 계속 실패하면 실행 환경을 바꿔야 할 수 있습니다.
- **수정된 게시물:** 이미 저장한 게시물의 본문이나 이미지가 바뀌어도 자동으로 반영하지 않습니다. 반영하려면 MongoDB에서 해당 문서를 삭제하세요. 다음 실행에서 최신 내용으로 다시 저장됩니다. 다른 프로젝트에서 이 컬렉션을 쓰는 방법은 [docs/SEXYITS2_CRAWL_HANDOFF.md](docs/SEXYITS2_CRAWL_HANDOFF.md)에 있습니다.
