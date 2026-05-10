# ⚡ AXILEX - Electrician Contractor Management System

A comprehensive, enterprise-level web application for managing electricians, jobs, tasks, materials, and payments.

## 🌐 Live Demo

**Live URL:** https://axilex-electrician.onrender.com

## 📋 Project Overview

The Electrician Contractor Management System is a full-stack web application designed to streamline the operations of electrical contracting businesses. It provides a centralized platform for managing electricians, assigning jobs and tasks, tracking progress, managing materials inventory, and handling payments through an integrated wallet system.

## ✨ Key Features

- **🔐 Authentication** - Secure login/register with role-based access (Admin/Electrician)
- **👥 Electrician Management** - Add, edit, delete, search, and filter electricians
- **📋 Job Management** - Create, assign, track jobs with deadlines and payment amounts
- **✅ Task Management** - Assign tasks, track progress (0-100%), update status
- **📦 Materials Management** - Track inventory, record material usage
- **💰 Payment System** - Wallet balance, send/receive payments, transaction history
- **📊 Reports** - Daily work reports, task completion stats, electrician activity
- **🔔 Notifications** - Real-time alerts for task assignments and completions
- **📱 Responsive UI** - Works on all devices (desktop, tablet, mobile)

## 🛠️ Technologies Used

| Category | Technologies |
|----------|--------------|
| Backend | Python, Flask, SQLite |
| Frontend | HTML5, CSS3, Bootstrap 5, JavaScript, Chart.js |
| Deployment | Render, Gunicorn |
| Security | SHA-256 hashing, Session management, Role-based access |

## 🗄️ Database Information

### About SQLite Database

This project uses **SQLite** as its database management system.

**Why SQLite?**
- Zero configuration - no separate database server needed
- File-based - easy backup and portability
- ACID compliant - reliable transactions
- Perfect for small to medium applications

**Database File:** `database.db` (created automatically in root directory)

**Database Tables:**

| Table | Purpose |
|-------|---------|
| users | User accounts, roles, wallet balances |
| electricians | Electrician profiles and status |
| jobs | Job details, assignments, amounts |
| tasks | Task assignments and progress |
| materials | Inventory items and quantities |
| payments | Transaction history |
| notifications | User alerts |
| daily_reports | Daily work summaries |

### ⚠️ Important Note for Deployment

**On Render (Cloud Platform):**
- SQLite database is **temporary** and **ephemeral**
- Data may reset when the server restarts or after new deployment
- This is **acceptable for project submission and demo purposes**
- For production use, consider switching to PostgreSQL

**On Local Machine:**
- Database persists permanently
- Located at `database.db` in the project root
- Data survives restarts and shutdowns

## 🚀 Installation & Setup

### Prerequisites
- Python 3.11 or higher
- pip (Python package manager)

### Step 1: Clone the Repository

```bash
git clone https://github.com/manasamashyal/axilex-electrician.git
cd axilex-electrician
