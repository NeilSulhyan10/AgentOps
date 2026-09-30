import { HTMLAttributes, forwardRef } from 'react'
import { cn } from '../../utils/helpers'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning'
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', ...props }, ref) => {
    const variants = {
      default: 'bg-primary-100 text-primary-800 dark:bg-primary-900/30 dark:text-primary-400',
      secondary: 'bg-dark-100 text-dark-800 dark:bg-dark-800 dark:text-dark-200',
      destructive: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      outline: 'border border-dark-300 text-dark-700 dark:border-dark-600 dark:text-dark-300',
      success: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    }

    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
          variants[variant],
          className
        )}
        {...props}
      />
    )
  }
)
Badge.displayName = 'Badge'