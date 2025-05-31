// Minor update
// Minor update
/**
 * Utility functions for form state persistence using localStorage
 * This helps prevent form data loss during token refresh cycles
 */

export interface FormPersistenceOptions {
  key: string;
  autoSave?: boolean;
  clearOnSuccess?: boolean;
  clearOnClose?: boolean;
}

/**
 * Hook for managing form state persistence
 */
export function useFormPersistence<T>(
  initialData: T,
  options: FormPersistenceOptions
) {
  const { key, autoSave = true, clearOnSuccess = true, clearOnClose = true } = options;

  // Initialize form data from localStorage or initial data
  const getInitialData = (): T => {
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.warn(`Failed to parse saved form data for key "${key}":`, e);
    }
    return initialData;
  };

  // Save form data to localStorage
  const saveFormData = (data: T) => {
    try {
      localStorage.setItem(key, JSON.stringify(data));
    } catch (e) {
      console.warn(`Failed to save form data for key "${key}":`, e);
    }
  };

  // Clear saved form data
  const clearFormData = () => {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.warn(`Failed to clear form data for key "${key}":`, e);
    }
  };

  return {
    getInitialData,
    saveFormData,
    clearFormData,
    autoSave,
    clearOnSuccess,
    clearOnClose
  };
}

/**
 * Generate a unique key for form data storage
 */
export function generateFormKey(prefix: string, identifier?: string | number): string {
  return identifier ? `${prefix}_${identifier}` : prefix;
}

/**
 * Common form keys for user management
 */
export const FORM_KEYS = {
  CREATE_USER: 'createUserFormData',
  EDIT_USER: (userId: number) => `editUserFormData_${userId}`,
  SET_PASSWORD: (userId: number) => `setPasswordFormData_${userId}`,
  RESET_PASSWORD: (userId: number) => `resetPasswordFormData_${userId}`,
} as const;

/**
 * Clear all user management form data
 */
export function clearAllUserFormData() {
  try {
    // Clear create user form
    localStorage.removeItem(FORM_KEYS.CREATE_USER);
    
    // Clear edit user forms (we need to iterate through all keys)
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.startsWith('editUserFormData_') || 
          key.startsWith('setPasswordFormData_') || 
          key.startsWith('resetPasswordFormData_')) {
        localStorage.removeItem(key);
      }
    });
  } catch (e) {
    console.warn('Failed to clear all user form data:', e);
  }
}

/**
 * Debug function to log all saved form data
 */
export function debugFormData() {
  try {
    const keys = Object.keys(localStorage);
    const formKeys = keys.filter(key => 
      key.includes('FormData') || 
      key.includes('User') || 
      key.includes('Password')
    );
    
    console.log('📋 Saved form data:');
    formKeys.forEach(key => {
      const data = localStorage.getItem(key);
      console.log(`  ${key}:`, data ? JSON.parse(data) : 'null');
    });
  } catch (e) {
    console.warn('Failed to debug form data:', e);
  }
} 