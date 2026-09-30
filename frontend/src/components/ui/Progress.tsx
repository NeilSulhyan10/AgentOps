import { HTMLAttributes, forwardRef } from 'react'
import { cn } from '../../utils/helpers'

interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value?: number
  max?: number
}

export const Progress = forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value = 0, max = 100, ...props }, ref) => {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

    return (
      <div
        ref={ref}
        className={cn('relative h-2 w-full overflow-hidden rounded-full bg-dark-200 dark:bg-dark-700', className)}
        {...props}
      >
        <div
          className="h-full bg-primary-600 transition-all duration-300 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
    )
  }
)
Progress.displayName = 'Progress'