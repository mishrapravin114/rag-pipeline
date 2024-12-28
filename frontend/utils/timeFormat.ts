// Minor update
// Minor update
import { format, formatDistanceToNow, isToday, isYesterday, isThisWeek, isThisYear, differenceInMinutes } from 'date-fns';

export const getRelativeTime = (date: Date): string => {
  const now = new Date();
  const diffInMinutes = differenceInMinutes(now, date);
  
  // Less than 1 minute
  if (diffInMinutes < 1) {
    return 'just now';
  }
  
  // Less than 1 hour
  if (diffInMinutes < 60) {
    return formatDistanceToNow(date, { addSuffix: true });
  }
  
  // Today
  if (isToday(date)) {
    return `Today at ${format(date, 'h:mm a')}`;
  }
  
  // Yesterday
  if (isYesterday(date)) {
    return `Yesterday at ${format(date, 'h:mm a')}`;
  }
  
  // This week
  if (isThisWeek(date)) {
    return format(date, 'EEEE \'at\' h:mm a');
  }
  
  // This year
  if (isThisYear(date)) {
    return format(date, 'MMM d \'at\' h:mm a');
  }
  
  // Older
  return format(date, 'MMM d, yyyy \'at\' h:mm a');
};

export const getFullTimestamp = (date: Date): string => {
  return format(date, 'PPpp'); // E.g., "Apr 29, 2023 at 3:30 PM"
};

export const getDateSeparatorText = (date: Date): string => {
  if (isToday(date)) {
    return 'Today';
  }
  
  if (isYesterday(date)) {
    return 'Yesterday';
  }
  
  if (isThisWeek(date)) {
    return format(date, 'EEEE');
  }
  
  if (isThisYear(date)) {
    return format(date, 'MMMM d');
  }
  
  return format(date, 'MMMM d, yyyy');
};

export const shouldShowDateSeparator = (currentDate: Date, previousDate: Date | null): boolean => {
  if (!previousDate) return true;
  
  return !isToday(currentDate) || !isToday(previousDate) || 
         format(currentDate, 'yyyy-MM-dd') !== format(previousDate, 'yyyy-MM-dd');
};