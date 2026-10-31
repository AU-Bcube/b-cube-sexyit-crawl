이 프로젝트는 매일 특정 계정(.env 참고)의 인스타그램 게시물을 크롤링해서 cloudflare r2와 mongodb에 저장한다.

# CRON 작업

- github actions를 사용한다.
- 현재 `sexyits2` collection의 인스타그램 게시물 id를 모두 가져온다.
- 매일 오전 08:00시에 인스타그램 게시물을 크롤링한다.
- 기존 저장된 게시물 id들과 크롤링해서 가져온 인스타그램 게시물 id를 대조해서 기존에 저장되어 있지 않던 새로운 인스타그램 게시물을 r2, mongodb에 저장한다.
- 인스타그램 계정에서 삭제된 게시물은 mongodb에서도 지운다. r2에서는 삭제하지 않는다.

# 참고

- 기존 방식은 mongodb의 `sexyits` collection
- 이 크롤러는 mongodb의 `sexyits2` collection 사용
- 기존 데이터를 마이그레이션할 필요가 없다. 새로운 콜렉션에 크롤링 자료만 저장되면 된다.
- 인스타그램 게시물을 가져올 때 가져올 수 있는 사진 중 가장 고화질을 가져온다.
- 인스타그램 크롤링 시 끝까지 크롤링해서 가져온다.
- nodejs 기반으로 작성하라. 인스타그램은 공개된 계정이므로 별도 인증 없이 크롤링한다.

# DB collection schema

- date: 업로드 시점
- title: 인스타그램 게시물의 첫번째 해시태그 문구(#을 제외한, 본문 어디에 있더라도 가져와야 함)
- imagePath: r2 업로드 주소 예. https://pub-11820c5f91164abc8e3e6e6bb3459741.r2.dev/sexyit2/... , $R2_DEV_ACCESS_PREFIX/$S3_PREFIX/...
- url: 인스타그램 주소URL
- ig_post_id: 인스타그램 게시물 id
