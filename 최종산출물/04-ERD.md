# 4. ERD (Entity Relationship Diagram)

기준: `backend/app/models.py` (SQLAlchemy ORM). 데이터베이스: PostgreSQL.

## 4.1 ERD 다이어그램

```mermaid
erDiagram
    USERS ||--o{ COMMENTS : "작성"
    USERS ||--o{ COMMENT_LIKES : "좋아요"
    USERS ||--o{ COMMENT_REPORTS : "신고"
    USERS ||--o{ SUBSCRIPTIONS : "구독"
    USERS ||--o{ BILLING_EVENTS : "결제이벤트"
    USERS ||--o{ USER_FAVORITE_ASSETS : "즐겨찾기"
    USERS ||--o| NOTIFICATION_PREFERENCES : "알림설정"
    USERS ||--o{ NOTIFICATION_CHANNEL_CONNECTIONS : "알림채널"
    USERS ||--o{ NOTIFICATION_RULES : "알림규칙"
    USERS ||--o{ NOTIFICATION_EVENTS : "알림이벤트"

    ASSETS ||--o{ AI_REPORTS : "리포트"
    ASSETS ||--o{ COMMENTS : "댓글대상"
    ASSETS ||--o{ USER_FAVORITE_ASSETS : "즐겨찾기대상"

    COMMENTS ||--o{ COMMENT_LIKES : "좋아요대상"
    COMMENTS ||--o{ COMMENT_REPORTS : "신고대상"

    SUBSCRIPTIONS ||--o{ BILLING_EVENTS : "관련결제"

    AI_REPORTS ||--o{ ASSET_NOTIFICATION_SNAPSHOTS : "최근리포트참조"

    USERS {
        int id PK
        string email UK
        string google_sub UK "nullable"
        string nickname UK
        datetime nickname_confirmed_at
        datetime created_at
    }
    ASSETS {
        int id PK
        enum category "AssetCategory"
        string ticker UK
        string name
    }
    AI_REPORTS {
        int id PK
        int asset_id FK
        text bull_summary
        text bear_summary
        text final_content
        string quality_status
        bool format_check_pass
        bool fact_check_pass
        bool qualitative_check_pass
        int revision_count
        datetime data_as_of
        json source_summary
        json analysis_framework
        json metadata_json
        datetime created_at
    }
    COMMENTS {
        int id PK
        int user_id FK
        int asset_id FK
        text content
        datetime created_at "KST"
    }
    COMMENT_LIKES {
        int user_id PK,FK
        int comment_id PK,FK
    }
    COMMENT_REPORTS {
        int user_id PK,FK
        int comment_id PK,FK
        datetime created_at
    }
    SUBSCRIPTIONS {
        int id PK
        int user_id FK
        string tier "FREE/PLUS/PRO"
        string status
        string provider
        string provider_subscription_id
        datetime current_period_end
        bool cancel_at_period_end
        datetime created_at
    }
    BILLING_EVENTS {
        int id PK
        string provider
        string provider_event_id
        string event_type
        string processed_status
        int subscription_id FK
        int user_id FK
        string payload_hash
        datetime received_at
    }
    USER_FAVORITE_ASSETS {
        int id PK
        int user_id FK
        int asset_id FK "nullable"
        string ticker
        string display_name
        string category_key
        string source
        datetime created_at
    }
    NOTIFICATION_PREFERENCES {
        int user_id PK,FK
        bool telegram_enabled
        bool email_enabled
        bool price_change_enabled
        bool news_enabled
        bool report_enabled
        bool daily_digest_enabled
        float price_change_threshold_percent
        string timezone
    }
    NOTIFICATION_CHANNEL_CONNECTIONS {
        int id PK
        int user_id FK
        string channel
        string destination
        bool verified
        string verification_status
        datetime created_at
    }
    NOTIFICATION_RULES {
        int id PK
        int user_id FK
        string ticker
        string event_type
        json threshold_json
        bool enabled
    }
    ASSET_NOTIFICATION_SNAPSHOTS {
        string ticker PK
        float last_price
        float last_change_percent
        json last_news_fingerprints
        int last_report_id FK
        datetime evaluated_at
    }
    NOTIFICATION_EVENTS {
        int id PK
        int user_id FK
        string ticker
        string event_type
        string severity
        string title
        text body
        string dedupe_key
        string status
        string channel
        int attempts
        datetime created_at
    }
```

## 4.2 엔티티 요약

| 테이블 | 역할 | 주요 키/제약 |
| --- | --- | --- |
| `users` | 사용자 계정 | `email`, `google_sub`, `nickname` 각 UNIQUE |
| `assets` | 금융 자산 메타 | `ticker` UNIQUE, `category` Enum |
| `ai_reports` | AI 투자 리포트 | `asset_id` FK, 품질 메타데이터 다수 |
| `comments` | 종목 토론 댓글 | `user_id`/`asset_id` FK, `created_at` KST |
| `comment_likes` | 댓글 좋아요 | 복합 PK (user_id, comment_id) |
| `comment_reports` | 댓글 신고 | 복합 PK (user_id, comment_id) |
| `subscriptions` | 구독 | (provider, provider_subscription_id) UNIQUE |
| `billing_events` | 결제 이벤트(멱등) | (provider, provider_event_id) UNIQUE |
| `user_favorite_assets` | 즐겨찾기 | (user_id, ticker) UNIQUE |
| `notification_preferences` | 알림 설정 | PK = user_id (1:1) |
| `notification_channel_connections` | 알림 채널 | (user_id, channel) UNIQUE |
| `notification_rules` | 알림 규칙 | user_id/ticker 인덱스 |
| `asset_notification_snapshots` | 알림 평가 스냅샷 | PK = ticker |
| `notification_events` | 알림 이벤트/발송 | (user_id, dedupe_key, channel) UNIQUE |

## 4.3 AssetCategory Enum

`INDEX`, `BOND_US`, `BOND_KR`, `STOCK_US`, `STOCK_KR`, `COMMODITY`, `CRYPTO`

> 모든 FK에는 사용자/자산 삭제 시 종속 데이터 정리를 위한 cascade(`all, delete-orphan`)가 다수 적용되어 있다(`models.py` relationship 정의 참조).
