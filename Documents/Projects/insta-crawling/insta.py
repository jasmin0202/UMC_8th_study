import instaloader

# Instaloader 인스턴스 생성
L = instaloader.Instaloader()

# 저장된 로그인 세션 불러오기
L.load_session_from_file("social069")

# 해시태그 지정
hashtag_name = "ootd"
hashtag = instaloader.Hashtag.from_name(L.context, hashtag_name)

# 추출할 최대 게시물 수
max_posts = 10

# 이미지 URL 저장 리스트
image_urls = []

# 게시물 순회하며 이미지 URL 수집
for i, post in enumerate(hashtag.get_posts(), start=1):
    print(f"\n📸 게시물 {i}")
    print(f"게시물 링크: https://www.instagram.com/p/{post.shortcode}/")
    print(f"이미지 링크: {post.url}")
    print(f"좋아요 수: {post.likes}")
    print(f"댓글 수: {post.comments}")

    image_urls.append(post.url)

    if i >= max_posts:
        break

# ✅ 전체 이미지 링크 출력
print("\n📂 전체 이미지 URL 리스트:")
for idx, url in enumerate(image_urls, start=1):
    print(f"{idx}: {url}")
