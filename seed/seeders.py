import asyncio
import json
import hashlib
import os
import re
import sys
import datetime
from datetime import timedelta
import random

# Ensure backend root is in system path so 'app' imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import db
from app.prisma_client import Json


def slugify(text: str) -> str:
    # Mirrors app/routers/blog_router.py slugify() exactly, so seeded slugs
    # are byte-identical to slugs the API would generate for the same title.
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}:{key.hex()}"


# ---------------------------------------------------------------------------
# Real, accurate exam questions (CCNA / CCNP / Networking / Cybersecurity)
# ---------------------------------------------------------------------------
EXAM_QUESTIONS = [
    # --- CCNA ---
    ("CCNA", "Which layer of the OSI model is responsible for logical addressing and routing?",
     ["Physical", "Data Link", "Network", "Transport"], "C",
     "The Network layer (Layer 3) handles logical addressing (IP addresses) and routing between networks."),
    ("CCNA", "What is the default subnet mask for a Class C IP address?",
     ["255.0.0.0", "255.255.0.0", "255.255.255.0", "255.255.255.255"], "C",
     "A Class C network uses the default mask 255.255.255.0 (/24), providing 256 addresses per network."),
    ("CCNA", "Which protocol is used to automatically assign IP addresses to devices on a network?",
     ["DNS", "DHCP", "ARP", "SNMP"], "B",
     "DHCP (Dynamic Host Configuration Protocol) automatically assigns IP addresses and other network configuration to hosts."),
    ("CCNA", "What is the purpose of VLSM (Variable Length Subnet Masking)?",
     ["To assign MAC addresses", "To allow different subnet masks within the same network to conserve address space",
      "To encrypt traffic", "To translate domain names"], "B",
     "VLSM lets a network be divided into subnets of different sizes, reducing wasted IP address space."),
    ("CCNA", "Which command displays the routing table on a Cisco router?",
     ["show interfaces", "show ip route", "show running-config", "show vlan"], "B",
     "'show ip route' displays the router's current IP routing table, including known networks and next hops."),
    ("CCNA", "What does STP (Spanning Tree Protocol) prevent?",
     ["IP address conflicts", "Switching loops", "DNS failures", "Duplicate MAC addresses"], "B",
     "STP prevents Layer 2 switching loops in redundant network topologies by blocking looped paths."),
    ("CCNA", "Which cable type is used to connect a router to a switch?",
     ["Crossover", "Straight-through", "Rollover", "Coaxial"], "B",
     "A straight-through cable is used to connect unlike devices such as a router to a switch."),
    ("CCNA", "What is the function of NAT (Network Address Translation)?",
     ["Encrypt data", "Translate private IP addresses to public IP addresses",
      "Assign VLANs", "Route between OSPF areas"], "B",
     "NAT translates private, internal IP addresses to a public IP address so devices can communicate on the internet."),
    ("CCNA", "Which port number does HTTPS use by default?",
     ["80", "21", "443", "25"], "C",
     "HTTPS (HTTP Secure) uses TCP port 443 by default."),
    ("CCNA", "What is the administrative distance of a directly connected route?",
     ["0", "1", "90", "110"], "A",
     "Directly connected routes have an administrative distance of 0, the most trusted route source."),
    ("CCNA", "Which protocol resolves IP addresses to MAC addresses?",
     ["DNS", "ARP", "DHCP", "ICMP"], "B",
     "ARP (Address Resolution Protocol) maps an IP address to the corresponding MAC address on a local network."),
    ("CCNA", "What is the maximum number of usable hosts in a /28 subnet?",
     ["14", "16", "30", "62"], "A",
     "A /28 subnet has 2^4 = 16 total addresses; subtracting the network and broadcast addresses leaves 14 usable hosts."),
    ("CCNA", "Which Cisco IOS command saves the running configuration to NVRAM?",
     ["copy running-config startup-config", "write erase", "show startup-config", "reload"], "A",
     "'copy running-config startup-config' saves the active configuration so it persists after a reboot."),

    # --- Networking ---
    ("Networking", "What does TCP use to establish a connection?",
     ["Two-way handshake", "Three-way handshake", "Four-way handshake", "No handshake"], "B",
     "TCP uses a three-way handshake (SYN, SYN-ACK, ACK) to establish a reliable connection."),
    ("Networking", "Which protocol operates at the transport layer and is connectionless?",
     ["TCP", "UDP", "IP", "ICMP"], "B",
     "UDP (User Datagram Protocol) is a connectionless transport-layer protocol with no delivery guarantees."),
    ("Networking", "What is the purpose of DNS?",
     ["Assign IP addresses", "Translate domain names to IP addresses", "Encrypt traffic", "Route packets"], "B",
     "DNS (Domain Name System) resolves human-readable domain names into IP addresses."),
    ("Networking", "Which port does DNS use by default?",
     ["53", "80", "443", "25"], "A",
     "DNS uses port 53 for both TCP and UDP traffic, most commonly UDP for standard queries."),
    ("Networking", "What is the function of a default gateway?",
     ["Assigns IP addresses", "Forwards traffic destined for networks outside the local subnet",
      "Filters MAC addresses", "Resolves hostnames"], "B",
     "The default gateway is the router a host sends traffic to when the destination is outside its local subnet."),
    ("Networking", "Which topology connects all devices to a central hub or switch?",
     ["Bus", "Ring", "Star", "Mesh"], "C",
     "In a star topology, every device connects individually to a central hub or switch."),
    ("Networking", "What does the acronym MTU stand for?",
     ["Maximum Transfer Unit", "Maximum Transmission Unit", "Minimum Transfer Unit", "Media Transfer Unit"], "B",
     "MTU (Maximum Transmission Unit) is the largest packet size that can be transmitted over a network link."),
    ("Networking", "Which protocol is used to send email?",
     ["POP3", "IMAP", "SMTP", "FTP"], "C",
     "SMTP (Simple Mail Transfer Protocol) is used to send and relay outgoing email."),
    ("Networking", "What is the loopback IP address in IPv4?",
     ["10.0.0.1", "127.0.0.1", "192.168.0.1", "172.16.0.1"], "B",
     "127.0.0.1 is the standard IPv4 loopback address used to test a device's own network stack."),
    ("Networking", "How many bits are in an IPv6 address?",
     ["32", "64", "128", "256"], "C",
     "An IPv6 address is 128 bits long, compared to 32 bits for IPv4."),
    ("Networking", "What does QoS (Quality of Service) manage on a network?",
     ["IP address assignment", "Prioritization of network traffic", "Domain name resolution", "Firewall rules"], "B",
     "QoS mechanisms prioritize certain types of traffic (e.g., voice or video) to ensure performance."),
    ("Networking", "Which device operates at Layer 2 of the OSI model and forwards frames based on MAC addresses?",
     ["Router", "Switch", "Hub", "Firewall"], "B",
     "A switch operates at Layer 2 and forwards Ethernet frames using MAC address tables."),
    ("Networking", "What is the purpose of the Time to Live (TTL) field in an IP packet?",
     ["Encrypt the packet", "Prevent packets from looping indefinitely by limiting hops",
      "Assign priority", "Compress payload"], "B",
     "TTL is decremented at each hop and the packet is discarded when it reaches zero, preventing infinite loops."),

    # --- Cybersecurity ---
    ("Cybersecurity", "What type of attack floods a system with traffic to make it unavailable?",
     ["Phishing", "Denial of Service (DoS)", "SQL Injection", "Man-in-the-middle"], "B",
     "A Denial of Service attack overwhelms a system with traffic or requests so legitimate users cannot access it."),
    ("Cybersecurity", "What is the primary purpose of a firewall?",
     ["Encrypt files", "Monitor and control incoming/outgoing network traffic based on rules",
      "Detect malware signatures", "Manage user accounts"], "B",
     "A firewall enforces a rule set to permit or deny network traffic between trusted and untrusted zones."),
    ("Cybersecurity", "What does the CIA triad in cybersecurity stand for?",
     ["Confidentiality, Integrity, Availability", "Control, Identity, Authentication",
      "Cryptography, Integrity, Auditing", "Confidentiality, Isolation, Authorization"], "A",
     "The CIA triad — Confidentiality, Integrity, and Availability — is the core model for information security."),
    ("Cybersecurity", "What is phishing?",
     ["A brute-force password attack", "A social engineering attack that tricks users into revealing sensitive information",
      "A type of firewall", "A network scanning technique"], "B",
     "Phishing uses deceptive messages, often emails, to trick victims into revealing credentials or sensitive data."),
    ("Cybersecurity", "What is the purpose of multi-factor authentication (MFA)?",
     ["Speeds up login", "Adds additional layers of verification beyond a password to confirm identity",
      "Encrypts network traffic", "Blocks malware"], "B",
     "MFA requires two or more independent credentials, greatly reducing the risk of compromised accounts."),
    ("Cybersecurity", "What is ransomware?",
     ["Software that displays ads", "Malware that encrypts a victim's files and demands payment for the decryption key",
      "A type of firewall", "A vulnerability scanner"], "B",
     "Ransomware encrypts a victim's data and extorts payment, typically in cryptocurrency, for the decryption key."),
    ("Cybersecurity", "What does a VPN primarily provide?",
     ["Faster internet speeds", "An encrypted tunnel for secure communication over a public network",
      "DNS resolution", "Malware protection"], "B",
     "A VPN (Virtual Private Network) creates an encrypted tunnel that protects data traveling over public networks."),
    ("Cybersecurity", "What is the purpose of an Intrusion Detection System (IDS)?",
     ["Block all traffic", "Monitor network or system activity for malicious activity and alert administrators",
      "Assign IP addresses", "Encrypt disk storage"], "B",
     "An IDS passively monitors traffic or hosts for suspicious activity and generates alerts."),
    ("Cybersecurity", "What is social engineering in the context of cybersecurity?",
     ["Designing secure networks", "Manipulating people into divulging confidential information or performing actions",
      "Writing malware code", "Configuring firewalls"], "B",
     "Social engineering exploits human psychology rather than technical vulnerabilities to gain access or information."),
    ("Cybersecurity", "What is the purpose of hashing a password before storing it?",
     ["To make it shorter", "To store a one-way transformed value that can't easily be reversed to the original password",
      "To encrypt it reversibly", "To compress the database"], "B",
     "Hashing produces a fixed-size, one-way value so the original password isn't stored or easily recoverable."),
    ("Cybersecurity", "What does SQL injection exploit?",
     ["Weak Wi-Fi encryption", "Improperly sanitized user input in database queries",
      "Outdated firmware", "Unpatched operating systems"], "B",
     "SQL injection inserts malicious SQL through unsanitized input fields to manipulate a backend database."),
    ("Cybersecurity", "What is the principle of least privilege?",
     ["Giving all users admin access", "Granting users only the access rights necessary to perform their job functions",
      "Encrypting all data", "Disabling all firewalls"], "B",
     "Least privilege minimizes risk by limiting each user or process to only the permissions it actually needs."),

    # --- CCNP ---
    ("CCNP", "What does BGP stand for?",
     ["Border Gateway Protocol", "Basic Gateway Protocol", "Backbone Gateway Protocol", "Bridge Gateway Protocol"], "A",
     "BGP (Border Gateway Protocol) is the path-vector protocol used to exchange routing information between autonomous systems on the internet."),
    ("CCNP", "Which routing protocol uses Autonomous System numbers to make routing decisions between different networks on the internet?",
     ["OSPF", "EIGRP", "BGP", "RIP"], "C",
     "BGP relies on AS numbers and path attributes to route traffic between autonomous systems."),
    ("CCNP", "What is the purpose of HSRP (Hot Standby Router Protocol)?",
     ["Load balance DNS requests", "Provide gateway redundancy by allowing multiple routers to act as a single virtual router",
      "Encrypt routing updates", "Assign VLANs dynamically"], "B",
     "HSRP provides first-hop router redundancy so hosts keep a consistent default gateway if one router fails."),
    ("CCNP", "What does OSPF use to calculate the shortest path?",
     ["Bellman-Ford algorithm", "Dijkstra's algorithm", "Distance vector calculation", "Hop count only"], "B",
     "OSPF is a link-state protocol that uses Dijkstra's Shortest Path First algorithm to build its routing tree."),
    ("CCNP", "What is route summarization used for?",
     ["Increasing routing table size", "Reducing the size of routing tables by combining multiple routes into a single advertisement",
      "Encrypting routes", "Blocking specific routes"], "B",
     "Route summarization advertises a single aggregate route instead of many specific routes, improving scalability."),
    ("CCNP", "In BGP, what is an Autonomous System (AS)?",
     ["A single router", "A collection of networks under a single administrative domain with a common routing policy",
      "A VLAN", "A firewall zone"], "B",
     "An AS is a network or group of networks managed under one administrative authority with a unified routing policy."),
    ("CCNP", "What is the purpose of Multiprotocol Label Switching (MPLS)?",
     ["Encrypt VPN traffic", "Direct data via labels instead of long network address lookups to speed up traffic flow",
      "Assign IP addresses", "Filter spam traffic"], "B",
     "MPLS forwards packets based on short labels rather than full routing table lookups, improving forwarding efficiency."),
    ("CCNP", "What does EIGRP stand for?",
     ["Enhanced Interior Gateway Routing Protocol", "External Interior Gateway Routing Protocol",
      "Enhanced Internet Gateway Routing Protocol", "Extended Interior Gateway Reporting Protocol"], "A",
     "EIGRP (Enhanced Interior Gateway Routing Protocol) is a Cisco advanced distance-vector routing protocol."),
    ("CCNP", "What is the function of Cisco StackWise technology?",
     ["Encrypts switch traffic", "Combines multiple physical switches into a single logical switch for simplified management",
      "Provides wireless connectivity", "Performs deep packet inspection"], "B",
     "StackWise links multiple physical switches together so they operate and are managed as one logical unit."),
    ("CCNP", "What is SD-WAN primarily designed to do?",
     ["Replace all physical routers", "Simplify the management and operation of a WAN by decoupling networking hardware from its control mechanism",
      "Provide antivirus protection", "Assign static IP addresses"], "B",
     "SD-WAN centralizes and simplifies WAN control and traffic steering independent of the underlying transport."),
    ("CCNP", "What is the purpose of Quality of Service (QoS) marking such as DSCP?",
     ["To encrypt packets", "To classify and prioritize traffic types across the network",
      "To assign VLAN IDs", "To perform NAT"], "B",
     "DSCP markings classify packets so network devices can apply consistent prioritization and forwarding treatment."),
    ("CCNP", "What does VRRP (Virtual Router Redundancy Protocol) provide, similar to HSRP?",
     ["Load balancing of web servers", "Gateway redundancy through a virtual router shared among multiple physical routers",
      "DNS failover", "Dynamic VLAN assignment"], "B",
     "VRRP is an open-standard protocol, similar to HSRP, that provides first-hop router redundancy."),
]


# ---------------------------------------------------------------------------
# Real interview-prep questions and answers
# ---------------------------------------------------------------------------
INTERVIEW_QUESTIONS = [
    {
        "topic": "CCNA",
        "questionText": "What is the primary purpose of OSPF (Open Shortest Path First)?",
        "correctAnswer": "OSPF is a link-state routing protocol used to find the best path for routing IP packets across a single IP network. It calculates the shortest path tree using Dijkstra's algorithm and maintains a topological map of the network."
    },
    {
        "topic": "CCNA",
        "questionText": "What is a VLAN and why is it used?",
        "correctAnswer": "A VLAN (Virtual LAN) is a logical grouping of devices on a network that act as if they are attached to the same broadcast domain, regardless of their physical location. VLANs are used to improve network security, manage broadcast traffic, and simplify network management."
    },
    {
        "topic": "Networking",
        "questionText": "Explain the main difference between TCP and UDP.",
        "correctAnswer": "TCP (Transmission Control Protocol) is connection-oriented, meaning it establishes a reliable connection and ensures that data packets are delivered in order without errors. UDP (User Datagram Protocol) is connectionless, meaning it sends packets without checking for delivery, making it faster but less reliable."
    },
    {
        "topic": "CCNA",
        "questionText": "What is a Default Gateway?",
        "correctAnswer": "A Default Gateway is a routing device (usually a router) used to forward all IP packets that are destined for an IP address outside of the local network/subnet."
    },
    {
        "topic": "Security",
        "questionText": "What is the difference between a Firewall and an Intrusion Prevention System (IPS)?",
        "correctAnswer": "A Firewall primarily relies on static rules to block or allow traffic based on ports and IP addresses. An IPS actively analyzes network traffic flows to detect and automatically prevent vulnerability exploits and malicious activity."
    },
    {
        "topic": "Networking",
        "questionText": "What is the purpose of a subnet mask?",
        "correctAnswer": "A subnet mask defines which portion of an IP address represents the network and which portion represents the host, allowing devices to determine whether another address is on the local network or must be reached via a router."
    },
    {
        "topic": "CCNA",
        "questionText": "What is the difference between a router and a switch?",
        "correctAnswer": "A switch operates at Layer 2 and forwards traffic within a local network based on MAC addresses. A router operates at Layer 3 and forwards traffic between different networks based on IP addresses, and can connect separate broadcast domains."
    },
    {
        "topic": "Security",
        "questionText": "What is the difference between symmetric and asymmetric encryption?",
        "correctAnswer": "Symmetric encryption uses a single shared key for both encryption and decryption, making it fast but requiring secure key distribution. Asymmetric encryption uses a public/private key pair, where data encrypted with the public key can only be decrypted with the private key, solving the key distribution problem at the cost of speed."
    },
    {
        "topic": "Security",
        "questionText": "What is a zero-day vulnerability?",
        "correctAnswer": "A zero-day vulnerability is a security flaw that is unknown to the vendor and has no available patch, meaning attackers can exploit it before defenders have had any time ('zero days') to fix it."
    },
    {
        "topic": "Cloud",
        "questionText": "What is the difference between IaaS, PaaS, and SaaS?",
        "correctAnswer": "IaaS (Infrastructure as a Service) provides virtualized compute, storage, and networking resources (e.g., AWS EC2). PaaS (Platform as a Service) provides a managed platform for developing and deploying applications without managing underlying infrastructure (e.g., AWS Elastic Beanstalk). SaaS (Software as a Service) delivers fully managed, ready-to-use applications over the internet (e.g., Gmail)."
    },
    {
        "topic": "Cloud",
        "questionText": "What is Amazon S3 used for?",
        "correctAnswer": "Amazon S3 (Simple Storage Service) is an object storage service used to store and retrieve any amount of data, such as backups, static website files, media, and logs, with high durability and availability."
    },
    {
        "topic": "Kubernetes",
        "questionText": "What is a Pod in Kubernetes?",
        "correctAnswer": "A Pod is the smallest deployable unit in Kubernetes, representing one or more tightly coupled containers that share the same network namespace, storage volumes, and lifecycle."
    },
    {
        "topic": "Kubernetes",
        "questionText": "What is the difference between a Deployment and a StatefulSet in Kubernetes?",
        "correctAnswer": "A Deployment manages stateless, interchangeable Pods and can freely create, replace, or scale them in any order. A StatefulSet manages stateful applications, giving each Pod a stable, unique identity and persistent storage that survives rescheduling, and creating/deleting Pods in a defined order."
    },
    {
        "topic": "DevOps",
        "questionText": "What is CI/CD?",
        "correctAnswer": "CI/CD stands for Continuous Integration and Continuous Delivery/Deployment. CI automates the process of merging and testing code changes frequently, while CD automates releasing that tested code to staging or production environments, enabling faster and more reliable software delivery."
    },
    {
        "topic": "Networking",
        "questionText": "What is the difference between a public and private IP address?",
        "correctAnswer": "A public IP address is globally unique and routable on the internet. A private IP address (e.g., ranges like 10.0.0.0/8 or 192.168.0.0/16) is only routable within a local network and requires NAT to communicate with the internet."
    },
]


# ---------------------------------------------------------------------------
# Blog posts — real, on-topic articles with suitable royalty-free cover images
# (Unsplash, matching the style already used for course thumbnails above).
# coverImage is a plain URL string, exactly what BlogPost.coverImage expects,
# so seeded posts and admin-uploaded local images ("/uploads/blog/...") render
# identically on the public Blog page.
# ---------------------------------------------------------------------------
BLOG_POSTS = [
    {
        "title": "CCNA 200-301: A Complete 8-Week Study Plan",
        "category": "CCNA",
        "readTime": "8 min read",
        "coverImage": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=1200&q=80",
        "excerpt": "A realistic week-by-week roadmap to pass the CCNA on your first attempt — covering IP fundamentals, routing, switching, security, and automation.",
        "content": (
            "Passing the CCNA 200-301 is less about raw study hours and more about structure.\n\n"
            "Weeks 1-2: Network fundamentals — the OSI and TCP/IP models, Ethernet, cabling, and IPv4 addressing. "
            "Do not move on until you can subnet in under 30 seconds.\n\n"
            "Weeks 3-4: Switching — VLANs, trunking, STP, and EtherChannel. Lab everything in Packet Tracer or CML.\n\n"
            "Weeks 5-6: Routing — static routes, OSPFv2, and first-hop redundancy. Learn to read 'show ip route' fluently.\n\n"
            "Week 7: Security fundamentals, wireless, and NAT/ACLs.\n\n"
            "Week 8: Automation, REST APIs, and full-length practice exams. Review every wrong answer until the reasoning sticks."
        ),
        "published": True,
    },
    {
        "title": "Cisco vs Juniper Certifications: Which Path Fits Your Career?",
        "category": "Career",
        "readTime": "6 min read",
        "coverImage": "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=1200&q=80",
        "excerpt": "Both vendors offer respected certification tracks — but they serve slightly different career strategies. Here's how to choose.",
        "content": (
            "Cisco certifications (CCNA, CCNP, CCIE) dominate enterprise job postings and are the safest default for "
            "most networking careers. The ecosystem, community, and study material are unmatched.\n\n"
            "Juniper certifications (JNCIA, JNCIS, JNCIP, JNCIE) carry serious weight in service-provider, ISP, and "
            "data-center environments where Junos is standard.\n\n"
            "Practical guidance: start with Cisco for breadth and market demand, then add Juniper if your target "
            "employers run Junos. The underlying protocols — OSPF, BGP, MPLS — are the same; only the CLI dialect changes. "
            "Engineers who can speak both are rare and get paid accordingly."
        ),
        "published": True,
    },
    {
        "title": "Subnetting Without Tears: The 5-Second Method",
        "category": "Networking",
        "readTime": "5 min read",
        "coverImage": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1200&q=80",
        "excerpt": "Stop drawing binary tables in the exam. This mental shortcut answers any subnetting question in seconds.",
        "content": (
            "Memorize one line: 128 192 224 240 248 252 254 255 — the mask values — and their block sizes: "
            "128 64 32 16 8 4 2 1.\n\n"
            "For any /n, find the 'interesting octet' (the one that isn't 0 or 255), take its block size, and the "
            "networks simply count up by that block. Example: /28 → mask 255.255.255.240 → block size 16 → "
            "subnets at .0, .16, .32... Usable hosts are always block size minus 2.\n\n"
            "Drill this daily for a week with random /25-/30 questions and subnetting becomes muscle memory — "
            "which is exactly what you need under exam time pressure."
        ),
        "published": True,
    },
    {
        "title": "Zero Trust Architecture: Beyond the Buzzword",
        "category": "Cybersecurity",
        "readTime": "7 min read",
        "coverImage": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1200&q=80",
        "excerpt": "'Never trust, always verify' sounds simple — implementing it isn't. What Zero Trust actually means for network engineers.",
        "content": (
            "Zero Trust replaces the castle-and-moat model with continuous verification: every request is "
            "authenticated, authorized, and encrypted regardless of where it originates.\n\n"
            "For network engineers this translates to concrete work: microsegmentation (VLANs and SGTs are your "
            "friends), identity-aware access (802.1X, RADIUS, posture checks), least-privilege ACLs everywhere, "
            "and telemetry — you cannot verify what you cannot see.\n\n"
            "Start small: segment your most critical asset first, enforce MFA on every management plane, and kill "
            "any flat Layer 2 domain that spans departments. Zero Trust is a direction of travel, not a product you buy."
        ),
        "published": True,
    },
    {
        "title": "BGP Path Selection Explained with Real Scenarios",
        "category": "CCNP",
        "readTime": "9 min read",
        "coverImage": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200&q=80",
        "excerpt": "Weight, local preference, AS-path, MED — the BGP best-path algorithm finally made intuitive, with scenarios you'll see in ENCOR and in production.",
        "content": (
            "BGP evaluates paths in strict order; the first tiebreaker that differs wins.\n\n"
            "1. Highest Weight (Cisco-local, affects only this router).\n"
            "2. Highest Local Preference (affects the whole AS — use it to prefer one exit point).\n"
            "3. Locally originated routes.\n"
            "4. Shortest AS-path (the one everyone remembers).\n"
            "5. Lowest origin code, then lowest MED, then eBGP over iBGP, then lowest IGP metric to the next hop.\n\n"
            "Scenario: dual-homed to two ISPs and outbound traffic favors the slow link? Raise Local Preference on "
            "routes learned from the fast ISP. Inbound traffic lopsided? Prepend your AS on advertisements out the "
            "link you want less used. Master these two levers and you can steer most real-world traffic problems."
        ),
        "published": True,
    },
    {
        "title": "From Help Desk to Network Engineer in 18 Months",
        "category": "Career",
        "readTime": "6 min read",
        "coverImage": "https://images.unsplash.com/photo-1573164713988-8665fc963095?w=1200&q=80",
        "excerpt": "A practical, no-fluff progression plan: certifications, home labs, and the projects that make hiring managers call back.",
        "content": (
            "Months 1-6: Earn the CCNA while you work. Volunteer for every network ticket that crosses the help "
            "desk queue — port security issues, VLAN moves, Wi-Fi complaints. That's free hands-on experience.\n\n"
            "Months 7-12: Build a home lab (used Catalyst switches are cheap; CML and EVE-NG are cheaper). Document "
            "three lab projects on GitHub or a blog: a segmented small-office network, an OSPF multi-area design, "
            "and a site-to-site VPN.\n\n"
            "Months 13-18: Start CCNP ENCOR, apply for NOC and junior network roles, and reference your documented "
            "projects in every interview. Employers hire proof, not promises — and a public lab portfolio is proof."
        ),
        "published": True,
    },
]


async def seed():
    print("Connecting to database...")
    await db.connect()

    print("Cleaning database...")
    await db.blogpost.delete_many()
    await db.payment.delete_many()
    await db.userprogress.delete_many()
    await db.userexamattempt.delete_many()
    await db.courseonlearningpath.delete_many()
    await db.learningpath.delete_many()
    await db.lesson.delete_many()
    await db.course.delete_many()
    await db.question.delete_many()
    await db.interviewquestion.delete_many()
    await db.user.delete_many()

    print("Seeding Users...")
    hashed_password = hash_password("user123")
    hashed_admin_password = hash_password("admin123")

    # Regular Free User
    free_user = await db.user.create(
        data={
            "email": "free@gordon.com",
            "passwordHash": hashed_password,
            "membershipLevel": "free"
        }
    )

    # Regular Premium User
    premium_user = await db.user.create(
        data={
            "email": "premium@gordon.com",
            "passwordHash": hashed_password,
            "membershipLevel": "premium"
        }
    )

    # Admin User
    admin_user = await db.user.create(
        data={
            "email": "admin@gordon.com",
            "passwordHash": hashed_admin_password,
            "membershipLevel": "premium"
        }
    )

    # Social Google User (Seeded dummy)
    google_user = await db.user.create(
        data={
            "email": "testgoogleuser@example.com",
            "googleId": "1234567890",
            "membershipLevel": "free"
        }
    )

    print("Seeding Courses & Lessons...")
    # Cloudinary sample videos or dummy video links
    video_1 = "https://res.cloudinary.com/demo/video/upload/sp_auto/dog.mp4"
    video_2 = "https://res.cloudinary.com/demo/video/upload/v1502283084/sea.mp4"
    video_3 = "https://res.cloudinary.com/demo/video/upload/v1612345678/sample.mp4"

    ccna = await db.course.create(
        data={
            "title": "CCNA 200-301 Complete Course",
            "description": "Master Cisco networking basics, routing, switching, and security protocols.",
            "thumbnailUrl": "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=500",
            "difficulty": "Beginner",
            "isPopular": True
        }
    )

    await db.lesson.create_many(
        data=[
            {
                "courseId": ccna.id,
                "title": "Introduction to Cisco CCNA 200-301",
                "videoUrl": video_1,
                "textContent": "Welcome to the CCNA course! In this lesson, we will cover the networking models, OSI, and TCP/IP protocol suites.",
                "orderIndex": 1
            },
            {
                "courseId": ccna.id,
                "title": "Understanding IPv4 Addressing & Subnetting",
                "videoUrl": video_2,
                "textContent": "Subnetting is the process of dividing a network into smaller sub-networks. We will cover CIDR notation, subnet masks, and broadcast domains.",
                "orderIndex": 2
            },
            {
                "courseId": ccna.id,
                "title": "Routing Protocols: OSPF & Static Routes",
                "videoUrl": video_3,
                "textContent": "Learn how routers forward packets. We will configure static routes and dynamic routing using Open Shortest Path First (OSPF).",
                "orderIndex": 3
            }
        ]
    )

    ccnp = await db.course.create(
        data={
            "title": "CCNP Enterprise ENCOR (350-401)",
            "description": "Advanced enterprise routing, switching, wireless, SD-WAN, and network automation.",
            "thumbnailUrl": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=500",
            "difficulty": "Advanced",
            "isPopular": True
        }
    )

    await db.lesson.create_many(
        data=[
            {
                "courseId": ccnp.id,
                "title": "Enterprise Network Architecture",
                "videoUrl": video_1,
                "textContent": "Analyze enterprise architecture designs, hierarchical layouts, high availability, and redundancy protocols like HSRP/VRRP.",
                "orderIndex": 1
            },
            {
                "courseId": ccnp.id,
                "title": "Deep Dive into BGP (Border Gateway Protocol)",
                "videoUrl": video_2,
                "textContent": "Explore eBGP, iBGP, path vector attributes, route reflection, and routing policies for enterprise scale.",
                "orderIndex": 2
            }
        ]
    )

    cyber = await db.course.create(
        data={
            "title": "Introduction to Cybersecurity Fundamentals",
            "description": "Learn the basics of cybersecurity, cryptography, risk management, and malware analysis.",
            "thumbnailUrl": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=500",
            "difficulty": "Intermediate",
            "isPopular": True
        }
    )

    await db.lesson.create_many(
        data=[
            {
                "courseId": cyber.id,
                "title": "Cybersecurity Threats & Vulnerabilities",
                "videoUrl": video_3,
                "textContent": "Understand threat actors, social engineering, malware categories (ransomware, trojans), and scanning networks for vulnerability.",
                "orderIndex": 1
            }
        ]
    )

    aws_saa = await db.course.create(
        data={
            "title": "AWS Solutions Architect Associate",
            "description": "Master AWS core services, architecture best practices, and exam objectives for the Solutions Architect Associate certification.",
            "thumbnailUrl": "https://images.unsplash.com/photo-1580106815433-a5b1d1d53d85?w=500",
            "difficulty": "Associate",
            "isPopular": True
        }
    )

    await db.lesson.create_many(
        data=[
            {
                "courseId": aws_saa.id,
                "title": "AWS Core Services Overview",
                "videoUrl": video_1,
                "textContent": "Get introduced to EC2, S3, VPC, and IAM — the foundational building blocks of AWS architecture.",
                "orderIndex": 1
            },
            {
                "courseId": aws_saa.id,
                "title": "Designing Resilient and Available Architectures",
                "videoUrl": video_2,
                "textContent": "Learn how to design highly available, fault-tolerant systems using multiple Availability Zones and Auto Scaling.",
                "orderIndex": 2
            }
        ]
    )

    k8s_prep = await db.course.create(
        data={
            "title": "Golden Kubestronaut",
            "description": "Interview and exam preparation Q&A for Kubernetes certification tracks.",
            "thumbnailUrl": "https://images.unsplash.com/photo-1634646809203-f3b4adff9127?w=500",
            "difficulty": "Advanced",
            "courseType": "PREPARATION"
        }
    )

    await db.lesson.create_many(
        data=[
            {
                "courseId": k8s_prep.id,
                "title": "Kubernetes Core Concepts Review",
                "videoUrl": video_3,
                "textContent": "Review Pods, Deployments, Services, and ConfigMaps ahead of certification exams and interviews.",
                "orderIndex": 1
            }
        ]
    )

    print("Seeding Learning Paths...")
    # Grouped by subject matter
    networking_path = await db.learningpath.create(
        data={
            "title": "Cisco Networking",
            "description": "Go from networking fundamentals to advanced enterprise routing and switching.",
            "pathType": "TOPIC",
        }
    )
    security_topic_path = await db.learningpath.create(
        data={
            "title": "Cybersecurity",
            "description": "Core security concepts, threats, and defensive fundamentals.",
            "pathType": "TOPIC",
        }
    )
    devops_path = await db.learningpath.create(
        data={
            "title": "DevOps",
            "description": "Cloud infrastructure, automation, and delivery pipelines.",
            "pathType": "TOPIC",
        }
    )
    ai_path = await db.learningpath.create(
        data={
            "title": "Artificial Intelligence",
            "description": "Foundational and applied AI topics.",
            "pathType": "TOPIC",
        }
    )
    k8s_path = await db.learningpath.create(
        data={
            "title": "Kubernetes",
            "description": "Container orchestration from fundamentals through certification prep.",
            "pathType": "TOPIC",
        }
    )

    # Grouped by job role — courses are deliberately reused across paths
    network_engineer_path = await db.learningpath.create(
        data={
            "title": "Network Engineer",
            "description": "The most in-demand Cisco career path — routing, switching, and enterprise design.",
            "pathType": "CAREER_TRACK",
        }
    )
    security_analyst_path = await db.learningpath.create(
        data={
            "title": "Security Analyst",
            "description": "Start with core networking, then specialize into threat analysis and defense.",
            "pathType": "CAREER_TRACK",
        }
    )
    devops_engineer_path = await db.learningpath.create(
        data={
            "title": "DevOps Engineer",
            "description": "Cloud infrastructure, CI/CD, and automation skills for modern DevOps roles.",
            "pathType": "CAREER_TRACK",
        }
    )
    cloud_engineer_path = await db.learningpath.create(
        data={
            "title": "Cloud Engineer",
            "description": "Design, deploy, and manage scalable cloud infrastructure.",
            "pathType": "CAREER_TRACK",
        }
    )

    await db.courseonlearningpath.create_many(
        data=[
            {"learningPathId": networking_path.id, "courseId": ccna.id, "orderIndex": 1},
            {"learningPathId": networking_path.id, "courseId": ccnp.id, "orderIndex": 2},
            {"learningPathId": security_topic_path.id, "courseId": cyber.id, "orderIndex": 1},
            {"learningPathId": devops_path.id, "courseId": aws_saa.id, "orderIndex": 1},
            {"learningPathId": k8s_path.id, "courseId": k8s_prep.id, "orderIndex": 1},
            {"learningPathId": network_engineer_path.id, "courseId": ccna.id, "orderIndex": 1},
            {"learningPathId": network_engineer_path.id, "courseId": ccnp.id, "orderIndex": 2},
            {"learningPathId": security_analyst_path.id, "courseId": ccna.id, "orderIndex": 1},
            {"learningPathId": security_analyst_path.id, "courseId": cyber.id, "orderIndex": 2},
            {"learningPathId": devops_engineer_path.id, "courseId": aws_saa.id, "orderIndex": 1},
            {"learningPathId": cloud_engineer_path.id, "courseId": aws_saa.id, "orderIndex": 1},
        ]
    )

    # Authored above as a letter (A/B/C/D) purely for readability — it must
    # be resolved to the actual option text before it's stored, since
    # correctOption has to match one of `options` verbatim for scoring to
    # work at all. Inserting the bare letter directly (the previous version
    # of this loop) is exactly what silently scored every practice exam
    # attempt as wrong regardless of what a student picked, no matter how
    # correct the frontend's comparison logic was.
    LETTER_TO_INDEX = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}

    print(f"Seeding Questions ({len(EXAM_QUESTIONS)} real exam questions)...")
    for idx, (cat, q_text, options, correct, explanation) in enumerate(EXAM_QUESTIONS, start=1):
        letter = correct.strip().upper()
        if letter not in LETTER_TO_INDEX or LETTER_TO_INDEX[letter] >= len(options):
            raise ValueError(
                f"Question #{idx} ({q_text!r}) has an invalid correct-answer letter {correct!r} "
                f"for its {len(options)} option(s) — fix the EXAM_QUESTIONS entry before reseeding."
            )
        correct_text = options[LETTER_TO_INDEX[letter]]

        await db.question.create(
            data={
                "category": cat,
                "questionText": q_text,
                "options": Json(options),
                "correctOption": correct_text,
                "explanation": explanation,
                "indexNumber": idx
            }
        )

    print(f"Seeding Interview Questions ({len(INTERVIEW_QUESTIONS)} real Q&A)...")
    for q in INTERVIEW_QUESTIONS:
        await db.interviewquestion.create(data=q)

    print("Seeding Payments & Extra Users...")
    premium_user_db = await db.user.find_unique(where={"email": "premium@gordon.com"})

    extra_emails = [
        "john.doe@example.com", "jane.smith@example.com", "alice.johnson@example.com",
        "bob.brown@example.com", "charlie.davis@example.com", "eva.white@example.com"
    ]

    base_date = datetime.datetime.now(datetime.timezone.utc)

    for i, email in enumerate(extra_emails):
        hashed_pwd = hash_password("pwd123")
        signup_offset = random.randint(10, 180)
        created_at = base_date - timedelta(days=signup_offset)

        user = await db.user.create(
            data={
                "email": email,
                "passwordHash": hashed_pwd,
                "membershipLevel": "premium" if i % 2 == 0 else "free",
                "createdAt": created_at
            }
        )

        if user.membershipLevel == "premium":
            plan = "yearly" if i % 3 == 0 else "monthly"
            amount = 120.00 if plan == "yearly" else 15.00
            payment_offset = signup_offset - random.randint(0, 2)
            payment_date = base_date - timedelta(days=payment_offset)

            await db.payment.create(
                data={
                    "userId": user.id,
                    "amount": amount,
                    "planType": plan,
                    "createdAt": payment_date
                }
            )

    if premium_user_db:
        await db.payment.create(
            data={
                "userId": premium_user_db.id,
                "amount": 120.00,
                "planType": "yearly",
                "createdAt": base_date - timedelta(days=120)
            }
        )

    print(f"Seeding Blog Posts ({len(BLOG_POSTS)} articles with cover images)...")
    for post in BLOG_POSTS:
        await db.blogpost.create(
            data={
                "title": post["title"],
                "slug": slugify(post["title"]),
                "excerpt": post["excerpt"],
                "content": post["content"],
                "category": post["category"],
                "coverImage": post["coverImage"],
                "readTime": post["readTime"],
                "published": post["published"],
            }
        )

    print("Database seeding completed successfully!")
    await db.disconnect()


# ---------------------------------------------------------------------------
# Merged from the former seed/fix_correct_options.py (that file is now
# retired — delete it). Same function name, same behavior, one entry point:
#
#   python seed/seeders.py                      -> full reseed
#   python seed/seeders.py fix-correct-options  -> data repair only
# ---------------------------------------------------------------------------
async def fix_correct_options():
    """
    One-time data repair, NOT a reseed. Every existing Question row is
    inspected; only rows where correctOption is a bare letter (A/B/C/D)
    that doesn't already match one of that question's options are updated,
    resolving the letter to the real option text at that position. Rows
    that are already correct are left untouched. Safe to run more than
    once — a second run will report everything as already correct and
    change nothing.

    This does not touch users, payments, courses, or any other table, and
    does not modify prisma/schema.prisma.
    """
    LETTER_TO_INDEX = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}

    print("Connecting to database...")
    await db.connect()

    questions = await db.question.find_many()
    print(f"Found {len(questions)} exam question(s). Checking correctOption integrity...\n")

    already_ok = 0
    fixed = 0
    unresolvable = []

    for q in questions:
        options = q.options or []
        current = (q.correctOption or "").strip()

        # Already correct: no action needed.
        if current in options:
            already_ok += 1
            continue

        # The known-broken pattern: correctOption is a bare position-letter
        # instead of the option text itself. Resolve it by index.
        letter = current.upper()
        if letter in LETTER_TO_INDEX and LETTER_TO_INDEX[letter] < len(options):
            real_answer = options[LETTER_TO_INDEX[letter]]
            await db.question.update(
                where={"id": q.id},
                data={"correctOption": real_answer}
            )
            print(f"  Fixed #{q.indexNumber} [{q.category}]: correctOption {current!r} -> {real_answer!r}")
            fixed += 1
        else:
            unresolvable.append(q)

    print(f"\nDone — {already_ok} already correct, {fixed} repaired.")

    if unresolvable:
        print(f"\n{len(unresolvable)} question(s) could NOT be auto-repaired")
        print("(correctOption isn't a recognized letter and doesn't match any option):\n")
        for q in unresolvable:
            print(f"  #{q.indexNumber} [{q.id}] category={q.category!r}")
            print(f"     correctOption={q.correctOption!r}")
            print(f"     options={q.options}")
        print("\nFix these manually: open the question via Edit on the dashboard's")
        print("Exam Questions page and re-pick the correct option from the list.")

    await db.disconnect()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("fix-correct-options", "fix_correct_options", "--fix-correct-options"):
        asyncio.run(fix_correct_options())
    else:
        asyncio.run(seed())