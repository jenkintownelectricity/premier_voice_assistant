# HIVE215 Mobile App

React Native app for iOS and Android built with Expo.

## Features

- User authentication (login/signup)
- Dashboard with usage stats
- Discount code redemption
- Dark theme with gold accents

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file from example:
```bash
cp .env.example .env
```

3. Add your Supabase credentials to `.env`

## Development

Start the development server:
```bash
npm start
```

Then:
- Press `i` for iOS simulator
- Press `a` for Android emulator
- Scan QR code with Expo Go app on your device

## Building for Production

### iOS

```bash
npx eas build --platform ios
```

### Android

```bash
npx eas build --platform android
```

## Project Structure

```
mobile/
├── App.tsx                 # Main entry point
├── src/
│   ├── lib/
│   │   ├── api.ts          # API client
│   │   ├── auth-context.tsx # Auth state management
│   │   ├── supabase.ts     # Supabase client
│   │   └── theme.ts        # Colors & spacing
│   └── screens/
│       ├── LoginScreen.tsx
│       ├── SignupScreen.tsx
│       ├── DashboardScreen.tsx
│       ├── RedeemScreen.tsx
│       └── SettingsScreen.tsx
└── assets/                  # Icons & images
```

## Requirements

- Node.js 18+
- Expo CLI
- iOS Simulator (Mac) or Android Emulator
- Expo Go app for physical device testing

## Testing on Your Phone

1. Download Expo Go from App Store / Play Store
2. Run `npm start`
3. Scan the QR code with:
   - iOS: Camera app
   - Android: Expo Go app
