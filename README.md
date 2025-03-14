# Tenders Ville API

Free, mobile-optimized tender information system for Kenya, providing real-time access to government tenders.

## API Endpoints

Base URL: `https://your-app-name.vercel.app`

### 1. Get Tenders
```http
GET /tenders?status=open&entity=ministry&category=services&days_remaining=7&page=1&limit=20
```

Parameters:
- `status`: Filter by status (open/closing_soon/closed)
- `entity`: Filter by procuring entity
- `category`: Filter by tender category
- `days_remaining`: Filter by days until closing
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20, max: 100)

### 2. Get Single Tender
```http
GET /tender/{tender_id}
```

### 3. Get Statistics
```http
GET /stats
```

### 4. Get Offline Bundle
```http
GET /offline-bundle
```
Returns cached tenders and stats for offline use.

## Mobile Features

1. **Offline Support**: Download tender bundles for offline access
2. **Mobile Optimization**: 
   - Truncated text for mobile screens
   - Optimized data transfer
   - Mobile-friendly date formats
3. **Low Bandwidth**: Compressed responses and efficient caching
4. **Location**: East Africa Time (EAT) timezone support

## Free Deployment on Vercel

1. Install Vercel CLI:
   ```bash
   npm install -g vercel
   ```

2. Login to Vercel:
   ```bash
   vercel login
   ```

3. Deploy:
   ```bash
   vercel
   ```

That's it! Your API will be live at `https://your-app-name.vercel.app`

### Vercel Free Tier Benefits:
- Serverless Functions: No server management needed
- Automatic HTTPS: SSL certificates included
- Global CDN: Fast access from anywhere
- Unlimited API Routes
- Generous Free Tier:
  - Unlimited Deployments
  - 100GB Bandwidth/month
  - Automatic CI/CD
  - No Credit Card Required

## Using in Your Mobile App

### React Native Example
```javascript
const API_URL = 'https://your-app-name.vercel.app';

// Get tenders
const getTenders = async () => {
  try {
    const response = await fetch(`${API_URL}/tenders?status=open`);
    const data = await response.json();
    return data.tenders;
  } catch (error) {
    console.error('Error fetching tenders:', error);
  }
};

// Get offline bundle
const getOfflineBundle = async () => {
  try {
    const response = await fetch(`${API_URL}/offline-bundle`);
    const bundle = await response.json();
    // Store in local storage
    await AsyncStorage.setItem('offlineBundle', JSON.stringify(bundle));
    return bundle;
  } catch (error) {
    console.error('Error fetching offline bundle:', error);
  }
};
```

### Flutter Example
```dart
final apiUrl = 'https://your-app-name.vercel.app';

// Get tenders
Future<List<Tender>> getTenders() async {
  try {
    final response = await http.get(Uri.parse('$apiUrl/tenders?status=open'));
    final data = json.decode(response.body);
    return data['tenders'];
  } catch (e) {
    print('Error fetching tenders: $e');
    throw e;
  }
}

// Get offline bundle
Future<Map<String, dynamic>> getOfflineBundle() async {
  try {
    final response = await http.get(Uri.parse('$apiUrl/offline-bundle'));
    final bundle = json.decode(response.body);
    // Store in shared preferences
    await prefs.setString('offlineBundle', json.encode(bundle));
    return bundle;
  } catch (e) {
    print('Error fetching offline bundle: $e');
    throw e;
  }
}
```

## API Documentation

Full API documentation is available at:
```
https://your-app-name.vercel.app/docs
```

## Support

For API support or issues:
1. Check the API status: `GET /`
2. View the API documentation: `/docs`
3. Test the offline bundle: `/offline-bundle`

## Contributing

This is a free, open-source project. Contributions are welcome!
