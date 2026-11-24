import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import type { ConsentStorage } from './consentStore';

// iOS Keychain / Android Keystore, this device only, excluded from backups.
// expo-secure-store has no web implementation, so the web preview uses localStorage.
export const secureConsentStorage: ConsentStorage = Platform.OS === 'web' ? {
  get: async key => globalThis.localStorage?.getItem(key) ?? null,
  set: async (key, value) => { globalThis.localStorage?.setItem(key, value); },
} : {
  get: key => SecureStore.getItemAsync(key),
  set: (key, value) => SecureStore.setItemAsync(key, value, { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY }),
};
