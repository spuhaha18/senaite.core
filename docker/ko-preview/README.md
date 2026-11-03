# 한국어 UI 미리보기 (Docker)

이 포크의 소스(한국어 번역 포함)로 SENAITE를 띄워 화면을 확인하는 방법입니다.

1. 이미지 빌드 (저장소 루트에서)

   ```bash
   docker build -f docker/ko-preview/Dockerfile -t senaite-ko-preview .
   ```

2. 실행

   ```bash
   docker run -d --name senaite-ko -p 8080:8080 senaite-ko-preview
   ```

3. 브라우저에서 http://localhost:8080 접속 → `admin` / `admin` 으로 로그인
   → 사이트 ID `senaite`, 기본 언어 **한국어**, 시간대 `Asia/Seoul` 선택 후 "Create SENAITE Site"

4. http://localhost:8080/senaite 에서 사용

참고
- 공식 2.6.0 런타임(Python 2.7 / Plone 5.2) 위에 이 포크의 `senaite.core`와
  GitHub 최신 애드온 소스를 덮어쓴 **검토용** 이미지입니다. 운영용이 아닙니다.
- 화면 캡처 예시는 `docs/screenshots-ko/` 에 있습니다.
