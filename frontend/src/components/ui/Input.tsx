import { forwardRef } from 'react'
import { cn } from '../../utils/helpers'

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'flex h-10 w-full rounded-lg border border-dark-300 bg-white px-4 py-2',
          'text-dark-900 placeholder:text-dark-400',
          'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'dark:border-dark-600 dark:bg-dark-800 dark:text-dark-100 dark:placeholder:text-dark-500',
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = 'Input'