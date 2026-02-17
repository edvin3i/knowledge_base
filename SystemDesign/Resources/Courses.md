---
tags:
  - system-design
  - courses
  - resources
created: 2026-02-17
---

# Онлайн-курсы и ресурсы по System Design / Online Courses and Resources

## Что это

Подборка лучших онлайн-ресурсов для изучения system design: платные платформы (Educative, ByteByteGo, O'Reilly, Udemy), YouTube-каналы (Gaurav Sen, Hussein Nasser, Arpit Bhayani), бесплатные ресурсы (System Design Primer, MIT 6.824), рассылки, платформы для практики и учебные пути (6-8 недель для собеседований, 3-6 месяцев для карьерного роста).

---

## Premium Platforms / Платные платформы

### Educative.io

**Website:** https://www.educative.io
**Price:** ~$59/month or ~$199/year
**Format:** Interactive text-based courses with embedded coding environments

#### Recommended Courses

| Course | Difficulty | Duration | Focus |
|--------|------------|----------|-------|
| **Grokking the System Design Interview** | Beginner-Intermediate | 20 hours | Interview preparation |
| **Grokking Modern System Design for Software Engineers** | Intermediate | 40 hours | Deep-dive into components |
| **Grokking the Advanced System Design Interview** | Advanced | 30 hours | Complex distributed systems |
| **Grokking the Object Oriented Design Interview** | Beginner | 15 hours | OOD patterns and principles |
| **Grokking Microservices Design Patterns** | Intermediate | 25 hours | Microservices architecture |

#### Why Educative?

- **Text-based learning** - Better for retention than video
- **Built-in diagrams** - Interactive system architecture visualizations
- **No video playback** - Learn at your own pace, easily reference sections
- **Coding exercises** - Practice implementations inline

#### Grokking the System Design Interview (Detailed)

**Best course for interview preparation.** Covers:

- Design a URL Shortening Service (TinyURL)
- Design Instagram
- Design Facebook Messenger
- Design Twitter
- Design YouTube/Netflix
- Design Uber
- Design Dropbox
- Design Twitter Search
- Design a Web Crawler
- Design Facebook's Newsfeed
- Design Yelp/Nearby Friends
- Design Ticketmaster

**Key Components Explained:**
- Load Balancing (round-robin, least connections, IP hash)
- Caching (cache-aside, write-through, write-behind)
- Data Partitioning (horizontal, vertical, directory-based)
- Replication (single-leader, multi-leader, leaderless)
- CAP Theorem and its practical implications
- Consistent Hashing

**Recommendation:** Start here if preparing for interviews.

---

### ByteByteGo

**Website:** https://bytebytego.com
**Author:** Alex Xu (System Design Interview author)
**Price:** ~$15/month or ~$79/year
**Format:** Newsletter + Video content

#### What's Included

- **Weekly Newsletter**: One system design topic deep-dive per week
- **Video Explanations**: Animated walkthroughs of complex systems
- **PDF Cheat Sheets**: Quick reference diagrams
- **Exclusive Content**: Content not in the books

#### Popular Topics Covered

- How Discord stores trillions of messages
- How Uber manages millions of writes/sec
- How Slack sends millions of messages
- How Netflix serves 200M+ subscribers
- Rate limiting algorithms comparison
- Database indexing explained
- API design best practices

#### Why ByteByteGo?

- **Visual Learning**: Excellent animated diagrams
- **Real-world Examples**: Based on actual tech company architectures
- **Regular Updates**: New content weekly
- **Author Credibility**: Alex Xu is the go-to system design author

**Recommendation:** Best value for ongoing learning and staying current.

---

### O'Reilly Learning Platform

**Website:** https://www.oreilly.com/online-learning/
**Price:** ~$49/month or ~$499/year (often discounted)
**Format:** Books, videos, live training, interactive labs

#### Key Benefits

- **Entire O'Reilly Library**: Thousands of books including DDIA, SRE Book, etc.
- **Video Courses**: From top instructors
- **Live Training Sessions**: Interactive workshops
- **Certifications Prep**: AWS, GCP, Kubernetes materials
- **Sandboxes**: Hands-on practice environments

#### Recommended Learning Paths

1. **Software Architecture Superstream**: Monthly live events on architecture
2. **Distributed Systems Path**: Curated content progression
3. **Cloud Native Path**: Kubernetes, Docker, microservices

**Recommendation:** Best for senior engineers wanting comprehensive access.

---

### Udemy

**Website:** https://www.udemy.com
**Price:** Usually $10-20 during sales (always wait for sales!)
**Format:** Video courses

#### Top System Design Courses

| Course | Instructor | Rating | Duration |
|--------|------------|--------|----------|
| **System Design Interview Guide** | Frank Kane | 4.6/5 | 8 hours |
| **Microservices Architecture** | Dimos Raptis | 4.5/5 | 12 hours |
| **Apache Kafka Series** | Stephane Maarek | 4.7/5 | 8+ hours |
| **Docker & Kubernetes** | Stephen Grider | 4.8/5 | 22 hours |

**Recommendation:** Good for specific technology deep-dives, wait for sales.

---

## YouTube Channels / YouTube-каналы

### System Design Interview

**Channel:** https://www.youtube.com/@SystemDesignInterview
**Subscribers:** 300K+
**Content:** System design problem walkthroughs
**Difficulty:** Beginner to Intermediate
**Free:** Yes

#### Popular Videos

- Design Uber (1M+ views)
- Design TikTok Recommendation
- Design Google Docs
- Design Rate Limiter

#### Why Watch?

- Clear explanations with whiteboard diagrams
- Interview-focused format (45-60 min problems)
- Covers both high-level and deep-dive aspects

---

### Gaurav Sen

**Channel:** https://www.youtube.com/@gaborwho
**Subscribers:** 600K+
**Content:** System design fundamentals + interview prep
**Difficulty:** Beginner to Intermediate
**Free:** Yes

#### Popular Playlists

- **System Design Basics**: Fundamentals series (start here)
- **System Design Problems**: URL shortener, WhatsApp, etc.
- **Distributed Systems**: Consensus, replication, partitioning

#### Notable Videos

- Consistent Hashing (1M+ views)
- System Design Primer (must-watch)
- CAP Theorem explained
- Database Sharding

#### Why Watch?

- Energetic teaching style
- Excellent for beginners
- Strong theoretical foundations

---

### Hussein Nasser

**Channel:** https://www.youtube.com/@haborwho
**Subscribers:** 500K+
**Content:** Backend engineering, databases, networking
**Difficulty:** Intermediate to Advanced
**Free:** Yes

#### Focus Areas

- Database internals (PostgreSQL, MySQL)
- Networking (TCP/UDP, HTTP/2, HTTP/3, WebSockets)
- Backend patterns and anti-patterns
- Real-world debugging and optimization

#### Notable Videos

- Why PostgreSQL is my favorite database
- HTTP/3 explained
- Connection pooling deep-dive
- Reverse proxy vs. Load balancer

#### Why Watch?

- Deep technical expertise
- Practical, production-focused content
- Explains "why" not just "what"

---

### Tech Dummies

**Channel:** https://www.youtube.com/@TechDummiesNarendr
**Subscribers:** 200K+
**Content:** System design interview preparation
**Difficulty:** Beginner to Intermediate
**Free:** Yes

#### Popular Content

- WhatsApp system design
- Netflix system design
- Tinder system design
- Instagram system design

---

### Arpit Bhayani

**Channel:** https://www.youtube.com/@AsliEngineering
**Subscribers:** 200K+
**Content:** Real-world engineering, database internals
**Difficulty:** Intermediate to Advanced
**Free:** Yes

#### Focus Areas

- Database engineering
- Real engineering problems from practice
- System design with implementation details

---

### Additional Channels

| Channel | Focus | Best For |
|---------|-------|----------|
| **Exponent** | Mock interviews | Interview practice |
| **Jordan has no life** | Database internals | Deep technical content |
| **Clement Mihailescu** | Interview prep | AlgoExpert founder |
| **NeetCode** | Coding + System Design | Combined prep |
| **ByteMonk** | System design | Quick explanations |

---

## Free Resources / Бесплатные ресурсы

### GitHub Repositories

#### System Design Primer

**Link:** https://github.com/donnemartin/system-design-primer
**Stars:** 260K+
**Content:** Comprehensive system design resource

**What's Included:**
- System design topics with explanations
- Study guides and flashcards
- Interview questions with solutions
- Scalability patterns

**Recommendation:** Best free resource. Bookmark and refer often.

---

#### Awesome System Design Resources

**Link:** https://github.com/ashishps1/awesome-system-design-resources
**Stars:** 15K+
**Content:** Curated list of system design resources

---

#### Awesome Scalability

**Link:** https://github.com/binhnguyennus/awesome-scalability
**Stars:** 50K+
**Content:** Scalability patterns and articles

---

### Engineering Blogs

| Company | Blog | Notable Topics |
|---------|------|----------------|
| **Netflix** | https://netflixtechblog.com | Microservices, resilience |
| **Uber** | https://eng.uber.com | Real-time systems, ML |
| **Meta** | https://engineering.fb.com | Scale, infrastructure |
| **Stripe** | https://stripe.com/blog/engineering | Payments, reliability |
| **Discord** | https://discord.com/blog/engineering | Real-time, databases |
| **Figma** | https://figma.com/blog/engineering | Collaboration, CRDTs |
| **Cloudflare** | https://blog.cloudflare.com | Networking, edge |
| **PlanetScale** | https://planetscale.com/blog | Database engineering |

**Recommendation:** Subscribe to RSS feeds. Real-world case studies are invaluable.

---

### Free Courses

| Course | Platform | Topic |
|--------|----------|-------|
| **MIT 6.824** | YouTube/MIT OCW | Distributed Systems |
| **Stanford CS144** | YouTube | Computer Networking |
| **CMU 15-445** | YouTube | Database Systems |
| **Google SRE Book** | sre.google | Site Reliability |

---

## Newsletters and Blogs / Рассылки и блоги

### Must-Subscribe Newsletters

| Newsletter | Frequency | Focus | Link |
|------------|-----------|-------|------|
| **ByteByteGo** | Weekly | System design | https://blog.bytebytego.com |
| **The Pragmatic Engineer** | Biweekly | Engineering leadership | https://newsletter.pragmaticengineer.com |
| **System Design Newsletter** | Weekly | System design | https://newsletter.systemdesign.one |
| **Architecture Notes** | Weekly | Architecture patterns | https://architecturenotes.co |
| **TLDR** | Daily | Tech news summary | https://tldr.tech |
| **Quastor** | Weekly | System design case studies | https://quastor.org |

---

## Practice Platforms / Платформы для практики

### Mock Interview Platforms

| Platform | Price | Feature |
|----------|-------|---------|
| **Pramp** | Free | Peer mock interviews |
| **Interviewing.io** | Paid | Anonymous interviews |
| **Exponent** | Paid | Company-specific prep |
| **Hello Interview** | Paid | AI-powered practice |

### Hands-on Labs

| Platform | Focus | Price |
|----------|-------|-------|
| **KodeKloud** | DevOps, Kubernetes | ~$20/month |
| **A Cloud Guru** | Cloud certifications | ~$35/month |
| **Katacoda** | Interactive scenarios | Free |
| **Play with Docker** | Docker practice | Free |

---

## Community Resources / Ресурсы сообщества

### Discord Servers

- **Educative.io Community** - Course discussions
- **ByteByteGo Community** - System design discussions
- **Tech Interview Discord** - Interview preparation

### Reddit Communities

| Subreddit | Members | Focus |
|-----------|---------|-------|
| r/ExperiencedDevs | 200K+ | Career growth |
| r/cscareerquestions | 900K+ | Career advice |
| r/softwarearchitecture | 50K+ | Architecture discussions |
| r/devops | 300K+ | DevOps practices |

### Slack Communities

- **Rands Leadership Slack** - Engineering leadership
- **Kubernetes Slack** - Kubernetes community
- **CNCF Slack** - Cloud native community

---

## Learning Paths / Учебные пути

### Interview Preparation (6-8 weeks)

```
Week 1-2: Fundamentals
├── Gaurav Sen YouTube (basics playlist)
├── System Design Primer (GitHub)
└── ByteByteGo newsletter (subscribe)

Week 3-4: Core Components
├── Educative: Grokking System Design
├── Practice: URL Shortener, Rate Limiter
└── YouTube: Specific system designs

Week 5-6: Advanced Topics
├── DDIA Chapters 5-9 (book)
├── Practice: Real-time systems, Search
└── Mock interviews (Pramp, peers)

Week 7-8: Polish & Practice
├── Mock interviews (2-3 per week)
├── Review weak areas
└── Company-specific preparation
```

### Career Growth Path (3-6 months)

```
Month 1: Foundations
├── Complete Grokking System Design (Educative)
├── Watch Gaurav Sen fundamentals
└── Read engineering blogs weekly

Month 2: Deep Dive
├── DDIA book (full read)
├── Hussein Nasser YouTube
└── Start hands-on projects

Month 3: Specialization
├── Choose area: Databases, Distributed, etc.
├── Take specialized course
└── Contribute to open source

Month 4-6: Application
├── Apply concepts at work
├── Write technical blog posts
├── Mentor others
```

### Free-Only Path

```
Phase 1: Foundation (2 weeks)
├── System Design Primer (GitHub)
├── Gaurav Sen YouTube
└── MIT 6.824 (distributed systems)

Phase 2: Practice (4 weeks)
├── YouTube system design videos
├── Engineering blog case studies
├── Pramp mock interviews (free)

Phase 3: Depth (4 weeks)
├── Google SRE Book (free online)
├── Specific technology deep-dives
└── Hands-on with Docker, Kubernetes
```

---

## Resource Comparison / Сравнение ресурсов

| Resource | Cost | Best For | Time Investment |
|----------|------|----------|-----------------|
| Educative | $$ | Interview prep | 20-40 hours |
| ByteByteGo | $ | Ongoing learning | 1-2 hours/week |
| YouTube | Free | Visual learners | Varies |
| System Design Primer | Free | Self-study | 10-20 hours |
| Engineering Blogs | Free | Real-world cases | 2-3 hours/week |
| O'Reilly | $$$ | Comprehensive | Unlimited |

---

## Quick Start Recommendations / Быстрый старт

### For Interview in 2 Weeks

1. **Educative**: Grokking System Design (speed run)
2. **GitHub**: System Design Primer (reference)
3. **YouTube**: Top 10 system design videos

### For Interview in 2 Months

1. **Educative**: Grokking System Design (complete)
2. **Book**: System Design Interview Vol 1 & 2
3. **Practice**: 20+ mock interviews

### For Long-term Growth

1. **Book**: DDIA (thorough study)
2. **Newsletter**: ByteByteGo + Pragmatic Engineer
3. **Practice**: Apply at work + side projects

---

## Связано с

- [[Glossary-SystemDesign]]
- [[Resources/Books]]
- [[Resources/Interview-Prep]]

## Ресурсы

1. Educative.io: https://www.educative.io
2. ByteByteGo: https://bytebytego.com
3. System Design Primer: https://github.com/donnemartin/system-design-primer
4. O'Reilly Learning: https://www.oreilly.com/online-learning/
5. Gaurav Sen YouTube: https://www.youtube.com/@gaborwho
6. Hussein Nasser YouTube: https://www.youtube.com/@haborwho
7. The Pragmatic Engineer Newsletter: https://newsletter.pragmaticengineer.com
